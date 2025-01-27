from datetime import datetime
import math
from pathlib import Path
import time
from typing import Any, Optional, Union, cast
from zoneinfo import ZoneInfo


import robin_stocks.robinhood as rh  # type: ignore [import-untyped]
from selenium import webdriver
from selenium.webdriver.common.by import By
from loguru import logger

from brokers import BASE_PATH, RH_LOGIN, RH_PASSWORD, RH_LOGIN2, RH_PASSWORD2
from utils.broker import Broker, StockOrder, OptionOrder
from pytz import utc, timezone
from utils.report.report import (
    OptionReportEntry,
    OptionType,
    OrderType,
    ReportEntry,
    StockData,
    ActionType,
    BrokerNames,
    OptionData,
    TwentyFourReportEntry
)
from utils.util import parse_option_string


class Robinhood(Broker):
    def _get_order_data(
        self, orderId: str
    ) -> list[tuple[float, float, float, str, str]]:
        res = []
        order_data = cast(dict, rh.get_stock_order_info(orderId))
        for execution in order_data["executions"]:
            res.append(
                (
                    execution["price"],
                    execution["quantity"],
                    execution["rounded_notional"],  # dollar amt
                    execution["timestamp"],
                    execution["id"],
                )
            )
        return res

    def buy(self, order: StockOrder) -> None:
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = self._get_current_time()

        res = self._market_buy(order)

        program_executed = datetime.now().strftime("%X:%f")  # when order went through
        post_stock_data = self._get_stock_data(order.sym)
        # print(res)

        # Maybe try this to fix robinhood id error
        if 'id' not in res:
            print("NO ID FOUND")
            for key in res:
                print(f"{key}  {res[key]}")
            print()
            # res["id"] = ''

        self._save_report(
            order.sym,
            ActionType.BUY,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
            order_id=res["id"],
            quantity=order.quantity,
        )

    def sell(self, order: StockOrder) -> None:
        
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = self._get_current_time()
        # print(f"Market Data: {pre_stock_data}")
        # print("About to sell")
        res = self._market_sell(order)
        # print("Sold")

        program_executed = datetime.now().strftime("%X:%f")  # when order went through
        post_stock_data = self._get_stock_data(order.sym)
        # print("Gotten Data")

        # if 'id' not in res:
        #     res["id"] = ''

        self._save_report(
            order.sym,
            ActionType.SELL,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
            order_id=res["id"],
            quantity=order.quantity,
        )
        # print("Saved report")

    def buy_option(self, order: OptionOrder) -> None:
        pre_stock_data = self._get_option_data(order)
        program_submitted = self._get_current_time()

        if order.option_type == OptionType.CALL:
            res = self._buy_call_option(order)
        else:
            res = self._buy_put_option(order)

        program_executed = self._get_current_time()  # when order went through
        post_stock_data = self._get_option_data(order)

        self._save_option_report(
            order,
            ActionType.BUY,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
            order_id=res["id"],
        )

    def sell_option(self, order: OptionOrder) -> None:
        pre_stock_data = self._get_option_data(order)
        program_submitted = self._get_current_time()

        if order.option_type == OptionType.CALL:
            res = self._sell_call_option(order)
        else:
            res = self._sell_put_option(order)
        program_executed = self._get_current_time()  # when order went through
        post_stock_data = self._get_option_data(order)

        self._save_option_report(
            order,
            ActionType.SELL,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
            order_id=res["id"],
        )

    def _limit_buy(self, order: StockOrder) -> dict:
        return cast(
            dict,
            rh.order_buy_limit(
                order.sym,
                order.quantity,
                order.price,
                timeInForce="gfd",
                extendedHours=False,
                jsonify=True,
            ),
        )

    def _limit_sell(self, order: StockOrder) -> dict:
        return cast(
            dict,
            rh.order_sell_limit(
                order.sym,
                order.quantity,
                order.price,
                timeInForce="gtc",
                extendedHours=False,
                jsonify=True,
            ),
        )

    def _market_buy(self, order: StockOrder) -> dict:
        if order.quantity < 1:
            res = (
                rh.order_buy_fractional_by_quantity(
                    order.sym,
                    order.quantity,
                    timeInForce="gfd",
                    extendedHours=False,
                    jsonify=True,
                ),
            )
        else:
            res = (
                rh.order_buy_market(
                    order.sym,
                    order.quantity,
                    timeInForce="gfd",
                    extendedHours=False,
                    jsonify=True,
                ),
            )
        return cast(dict, res[0])

    def _market_sell(self, order: StockOrder) -> dict:
        if order.quantity < 1:
            res = (
                rh.order_sell_fractional_by_quantity(
                    order.sym,
                    order.quantity,
                    timeInForce="gfd",
                    extendedHours=False,
                    jsonify=True,
                ),
            )
        else:
            res = (
                rh.order_sell_market(
                    order.sym,
                    order.quantity,
                    timeInForce="gfd",
                    extendedHours=False,
                    jsonify=True,
                ),
            )
        return cast(dict, res[0])

    def _handle_option_tick_size(self, action: ActionType, price: float) -> float:
        return self._round_to_nearest(action, price, 0.05)

    def _round_to_nearest(
        self, action: ActionType, price: float, nearest: float
    ) -> float:
        if price / nearest >= 1:
            return round(
                (
                    math.ceil(price / nearest) * nearest
                    if action == ActionType.OPEN
                    else math.floor(price / nearest) * nearest
                ),
                2,
            )
        else:
            return price

    def _buy_call_option(self, order: OptionOrder) -> dict:
        limit_price = round(
            float(self._get_option_data(order).ask) * 1.03,
            2,
        )
        limit_price = self._handle_option_tick_size(ActionType.OPEN, limit_price)

        return self._perform_option_trade(
            ActionType.OPEN,
            OptionType.CALL,
            order.sym,
            limit_price,
            float(order.strike),
            order.expiration,
            order.quantity,
        )

    def _sell_call_option(self, order: OptionOrder) -> dict:
        limit_price = round(
            float(self._get_option_data(order).bid) * 0.97,
            2,
        )
        limit_price = self._handle_option_tick_size(ActionType.CLOSE, limit_price)

        return self._perform_option_trade(
            ActionType.CLOSE,
            OptionType.CALL,
            order.sym,
            limit_price,
            float(order.strike),
            order.expiration,
            order.quantity,
        )

    def _buy_put_option(self, order: OptionOrder) -> dict:
        limit_price = round(
            float(self._get_option_data(order).ask) * 1.03,
            2,
        )
        limit_price = self._handle_option_tick_size(ActionType.OPEN, limit_price)

        return self._perform_option_trade(
            ActionType.OPEN,
            OptionType.PUT,
            order.sym,
            limit_price,
            float(order.strike),
            order.expiration,
            order.quantity,
        )

    def _sell_put_option(self, order: OptionOrder) -> dict:
        limit_price = round(
            float(self._get_option_data(order).bid) * 0.97,
            2,
        )
        limit_price = self._handle_option_tick_size(ActionType.CLOSE, limit_price)

        return self._perform_option_trade(
            ActionType.CLOSE,
            OptionType.PUT,
            order.sym,
            limit_price,
            float(order.strike),
            order.expiration,
            order.quantity,
        )

    def _perform_option_trade(
        self,
        action: ActionType,
        optionType: OptionType,
        sym: str,
        limit_price: float,
        strike: float,
        expiration: str,
        quantity: int,
    ) -> dict:
        """
        expiration: "YYYY-MM-DD"
        """
        positionEffect = (
            ActionType.OPEN.value
            if action == ActionType.OPEN
            else ActionType.CLOSE.value
        )
        option_type: str = (
            OptionType.CALL.value
            if optionType == OptionType.CALL
            else OptionType.PUT.value
        )
        if action == ActionType.OPEN:
            res = rh.order_buy_option_limit(
                positionEffect=positionEffect,
                creditOrDebit="debit",
                price=limit_price,
                symbol=sym,
                quantity=quantity,
                expirationDate=expiration,
                strike=strike,
                optionType=option_type,
                timeInForce="gfd",
                jsonify=True,
            )
        else:
            res = rh.order_sell_option_limit(
                positionEffect=positionEffect,
                creditOrDebit="credit",
                price=limit_price,
                symbol=sym,
                quantity=quantity,
                expirationDate=expiration,
                strike=strike,
                optionType=option_type,
                timeInForce="gfd",
                jsonify=True,
            )
        return cast(dict, res)

    def _get_stock_data(self, sym: str) -> StockData:
        stock_data: Any = cast(dict, rh.stocks.get_quotes(sym))[0]
        return StockData(
            stock_data["ask_price"],
            stock_data["bid_price"],
            rh.stocks.get_latest_price(sym)[0],
            cast(dict, rh.stocks.get_fundamentals(sym, info="volume"))[0],
        )

    def _get_option_data(self, order: OptionOrder) -> OptionData:
        option_data: list = cast(
            list,
            rh.find_options_by_expiration_and_strike(
                order.sym,
                order.expiration,
                str(order.strike),
                order.option_type.value,
            ),
        )
        data = option_data[0]
        return OptionData(
            data["ask_price"],
            data["bid_price"],
            data["last_trade_price"],
            data["volume"],
            data["implied_volatility"],
            data["delta"],
            data["theta"],
            data["gamma"],
            data["vega"],
            data["rho"],
            None,  # (RH does not provide underlying price)
            None,  # (RH does not provide in the money status)
        )

    def _save_report(
        self,
        sym: str,
        action_type: ActionType,
        program_submitted: str,
        program_executed: str,
        pre_stock_data: StockData,
        post_stock_data: StockData,
        **kwargs: Union[float, str],
    ) -> None:
        self._add_report_to_file(
            ReportEntry(
                program_submitted,
                program_executed,
                None,
                sym,
                action_type,
                cast(float, kwargs["quantity"]),
                None,  # (RH price is added when generating report)
                None,  # (RH dollar_amt is added when generating report)
                pre_stock_data,
                post_stock_data,
                OrderType.MARKET,
                False,
                cast(str, kwargs["order_id"]),
                None,
                BrokerNames.RH,
            )
        )
        self._save_report_to_file()

    def _save_option_report(
        self,
        order: OptionOrder,
        action_type: ActionType,
        program_submitted: str,
        program_executed: str,
        pre_stock_data: OptionData,
        post_stock_data: OptionData,
        **kwargs: str,
    ) -> None:
        self._add_option_report_to_file(
            OptionReportEntry(
                program_submitted,
                program_executed,
                None,
                order.sym,
                order.strike,
                order.option_type,
                order.expiration,
                action_type,
                order.quantity,
                None,  # (RH price is added when generating report)
                pre_stock_data,
                post_stock_data,
                OrderType.LIMIT,  # (RH only allows limit orders for options)
                None,
                kwargs["order_id"],
                None,
                BrokerNames.RH,
            )
        )

        self._save_option_report_to_file()

    def __init__(
        self,
        report_file: Path,
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        super().__init__(report_file, broker_name, option_report_file)

    def login(self) -> None:
        """
        if changing the login credentials go to your (HOME_DIR)/.tokens and delete the robinhood.pickle file
        :return: None
        """
        Robinhood.login_custom(account="RH")

    @staticmethod
    def login_custom(account: str = "RH") -> None:
        account = account.upper()
        pickle_file = "1" if account == "RH" else "2"
        username = RH_LOGIN if account == "RH" else RH_LOGIN2
        password = RH_PASSWORD if account == "RH" else RH_PASSWORD2
        time_logged_in = 60 * 60 * 24 * 365
        rh.authentication.login(
            username=username,
            password=password,
            expiresIn=time_logged_in,
            scope="internal",
            by_sms=True,
            pickle_name=pickle_file,
        )

    def get_current_positions(self) -> tuple[list[StockOrder], list[OptionOrder]]:
        current_positions: list[StockOrder] = []
        positions = rh.account.build_holdings()
        for sym in positions:
            current_positions.append(StockOrder(sym, float(positions[sym]["quantity"])))
        return current_positions, []

    def download_trade_confirmations(self) -> None:
        documents = rh.account.get_documents()
        if not documents:
            return
        dir = str(BASE_PATH / "data/rh") + "/"
        cutoff = datetime(2023, 9, 1)
        for doc in documents:
            if doc["type"] == "trade_confirm":
                year, month, day = doc["date"].split("-")
                if datetime(int(year), int(month), int(day)) < cutoff:
                    continue    
                filename = f"rh_{month}_{day}_{year[2:]}"
                try:
                    rh.account.download_document(doc["download_url"], filename, dir)
                except:
                    print(f"Error downloading {filename}")


# ----------------------------------------------------------------------------------------------------------------------------
# 24 Hour Trading Methods

    '''
    Buys and Sells symbol immediately
    Adds to report
    '''
    def buy_and_sell_immediately(self, symbol):

        market_hours_flag = self.get_correct_market_flag()

        try:
            buy_program_submitted = datetime.now().strftime("%I:%M:%S %p")
            buy_id = self.buy_limit(symbol, market_hours_flag)
            logger.info(f"Bought {symbol} on Robinhood")

            sell_program_submitted = datetime.now().strftime("%I:%M:%S %p")
            sell_id = self.sell_limit(symbol, market_hours_flag)
            logger.info(f"Sold {symbol} on Robinhood")
        except Exception as e:      # ADD IN THE ACTUAL EXCEPTION THAT HAPPENS WHEN ORDER GETS REJECTED
            logger.info("Exception Caught on Robinhood:")
            print(e)
            self.add_rejected_order_to_report(symbol, buy_program_submitted)
            return

        try:
            self.add_to_24_hour_report(buy_id, sell_id, symbol, buy_program_submitted, sell_program_submitted)
        except Exception as e:
            logger.info("Exception Caught while adding to report")
            # likely unable to pull data
            # so, add to report but leave price blank


    '''
    Gets correct market data parameter based on current time
    Required as parameter on robinhood buy/sell function
    '''
    def get_correct_market_flag(self):
        from datetime import time
        # Get the current time
        current_time = datetime.now().time()

        # Define the time ranges
        extended_morning_start = time(4, 0)  # 4:00 AM
        extended_morning_end = time(6, 30)  # 6:30 AM
        extended_afternoon_start = time(13, 0)  # 1:00 PM
        extended_afternoon_end = time(16, 0)  # 4:00 PM
        all_day_start = time(16, 0)  # 4:00 PM
        all_day_end = time(4, 0)  # 4:00 AM (next day)

        # Check the conditions
        if (extended_morning_start <= current_time <= extended_morning_end or
            extended_afternoon_start <= current_time <= extended_afternoon_end):
            return "extended_hours"
        elif (current_time >= all_day_start or current_time < all_day_end):
            return "all_day_hours"
        else:
            return "regular_hours"

        return ""


    '''
    Buys an extended/after hours limit order
    Return order id in order to pull data later
    '''
    def buy_limit(self, symbol, market_hours_flag):

        limit_price = round(
                float(rh.stocks.get_quotes(symbol)[0]["ask_price"]) * 1.05,
                2,
            )
        
        extended_hours_flag = True
        if market_hours_flag == 'regular_hours':
            extended_hours_flag = False
        
        res = rh.order( symbol = symbol,
                        quantity = 1,
                        side = "buy",
                        limitPrice = limit_price,
                        extendedHours = extended_hours_flag,
                        timeInForce="gfd",
                        market_hours = market_hours_flag)
        
        
        
        # try:
        #     order_id = res['id']
        # except Exception as e:
        #     print(e)
        #     print()
        #     print(res)


        order_id = res['id']
        # print(res)
        return order_id
   

    '''
    Sells an extended/after hours limit order
    Return order id in order to pull data later
    '''
    def sell_limit(self, symbol, market_hours_flag):
        limit_price = round( float(rh.stocks.get_quotes(symbol)[0]["ask_price"]) * 0.95,
                             2)

        extended_hours_flag = True
        if market_hours_flag == 'regular_hours':
            extended_hours_flag = False

        res = rh.order( symbol = symbol,
                        quantity = 1,
                        side = "sell",
                        limitPrice = limit_price,
                        extendedHours = extended_hours_flag,
                        timeInForce="gfd",
                        market_hours = market_hours_flag)
        
        order_id = res['id']
        return order_id
    

    '''
    Adds the buy and sell trades to the report
    '''
    def add_to_24_hour_report(self, buy_id, sell_id, symbol, buy_submitted_time, sell_submitted_time):

        logger.info("About to create entries")
        # get prices, create report entries
        buy_price, buy_report_entry = self.create_24_hour_report_entry(buy_id, symbol, "BUY", buy_submitted_time)
        sell_price, sell_report_entry = self.create_24_hour_report_entry(sell_id, symbol, "SELL", sell_submitted_time)
        logger.info("Created entries")

        print("RH")
        print(buy_price)
        print(sell_price)

        # calculate and add spread to report entries
        spread_value =  float(buy_price) - float(sell_price)
        buy_report_entry.spread = spread_value
        sell_report_entry.spread = spread_value

        logger.info("Writing to csv")
        # write to report file
        date = datetime.now().strftime("%m_%d")
        report_file = BASE_PATH / f"reports/24_hour/24_report_{date}.csv"
        with report_file.open("a") as file:
            file.write(str(buy_report_entry))
            file.write(str(sell_report_entry))

        

    '''
    Creates report entry objects
    Requires the trade id in order to pull price and execution time from API

    Returns price so we can calculate spread later and add it to report
    '''
    def create_24_hour_report_entry(self, id, symbol, action, submit_time):

        time.sleep(1)
        order_data = rh.get_stock_order_info(id)

        # print(order_data)
        # logger.info("Before error points")

        # if can't pull execution data, try again!
        if len(order_data['executions']) == 0:
            time.sleep(2)
            order_data = rh.get_stock_order_info(id)
        price = str(round(float(order_data['executions'][0]['price']), 2))          # get price

        # logger.info("In between error points")
        # get and format broker executed time
        utc_time = datetime.strptime(
            order_data["executions"][0]["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        now_aware = utc.localize(utc_time)
        pst = now_aware.astimezone(timezone("US/Pacific"))
        broker_executed_time = pst.strftime("%I:%M:%S %p")

        # logger.info("After error points")


        report_entry = TwentyFourReportEntry(
                        date=datetime.today().strftime("%m/%d/%Y"),
                        program_submitted=submit_time,
                        broker_executed=broker_executed_time,
                        sym=symbol,
                        broker='RH',
                        action=action,
                        quantity=1,
                        price=price,
                        spread=None
                        )

        return price, report_entry
    
    '''
    Adds orders that get rejected to the report
    Sets price + spread to 0 to indicate rejection
    '''
    def add_rejected_order_to_report(self, symbol, submit_time):
        buy_report_entry = TwentyFourReportEntry(
                            date=datetime.today().strftime("%m/%d/%Y"),
                            program_submitted=submit_time,
                            broker_executed=submit_time,
                            sym=symbol,
                            broker='RH',
                            action="BUY",
                            quantity=1,
                            price=0,
                            spread=0
                            )
        
        sell_report_entry = TwentyFourReportEntry(
                            date=datetime.today().strftime("%m/%d/%Y"),
                            program_submitted=submit_time,
                            broker_executed=submit_time,
                            sym=symbol,
                            broker='RH',
                            action="SELL",
                            quantity=1,
                            price=0,
                            spread=0
                            )
        
        # write to report file
        date = datetime.now().strftime("%m_%d")
        report_file = BASE_PATH / f"reports/24_hour/24_report_{date}.csv"
        with report_file.open("a") as file:
            file.write(str(buy_report_entry))
            file.write(str(sell_report_entry))

    def get_ask_price(self, symbol):
        return round(float(rh.stocks.get_quotes(symbol)[0]["ask_price"]), 2)
    
    def get_bid_price(self, symbol):
        return round(float(rh.stocks.get_quotes(symbol)[0]["bid_price"]), 2)
        

        
    


if __name__ == "__main__":
    r = Robinhood(Path("temp.csv"), BrokerNames.RH, Path("temp_option.csv"))
    r.login()

    # option = OptionOrder(sym='MU', option_type=OptionType.CALL, strike='107.00', expiration='2025-01-31', order_type=OrderType.MARKET, quantity=1)
    # r.sell_option(option)

    # r.buy_limit("NVDA")
    # r.sell_limit("NVDA")
    # print("ROBINHOOD")
    # def print_bid_and_ask(symbols):
    #     for symbol in symbols:
    #         print(symbol)
    #         print(r.get_bid_price(symbol))
    #         print(r.get_ask_price(symbol))
    #         print('-----------------------------------')

    # sym_list = ["AAPL", "AMZN"]
    # print_bid_and_ask(sym_list)

    # print(r.get_ask_price("BBY"))
    # print(r.get_bid_price("BBY"))


    # print(r.get_correct_market_flag())
    # r.buy_and_sell_immediately("GME")


