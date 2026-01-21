from datetime import datetime, time
from zoneinfo import ZoneInfo
import math
from pathlib import Path
import time
from typing import Any, Optional, Union, cast
from zoneinfo import ZoneInfo
import traceback
import schedule
import sys
import re


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
from utils.selenium_helper import CustomChromeInstance
from utils.util import convert_date


class Robinhood2(Broker):
    def __init__(self, report_file: Path, broker_name: BrokerNames, option_report_file: Optional[Path] = None):
            
        super().__init__(report_file, broker_name, option_report_file)
        self._broker_name = broker_name
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open(
            "https://robinhood.com/login/"
        )


    
    def login(self) -> None:
        """
        Enter the username and password into RH site to login!
        """
        time.sleep(3)

        login_input_elem = self._chrome_inst.find(By.XPATH, '//*[@id="react_root"]/div[1]/div[2]/div/div/div[2]/div[2]/div/form/div/div[1]/label/div[2]/input')
        self._chrome_inst.sendKeyboardInput(login_input_elem, RH_LOGIN)
        time.sleep(1)

        password_input_elem = self._chrome_inst.find(By.XPATH, '//*[@id="current-password"]')
        self._chrome_inst.sendKeyboardInput(password_input_elem, RH_PASSWORD)
        time.sleep(1)

        keep_me_logged_in_button = self._chrome_inst.find(By.XPATH, '//*[@id="react_root"]/div[1]/div[2]/div/div/div[2]/div[2]/div/form/div/div[3]/label/div/div/div')
        keep_me_logged_in_button.click()
        time.sleep(1)

        login_button = self._chrome_inst.find(By.XPATH, '//*[@id="react_root"]/div[1]/div[2]/div/div/div[2]/div[2]/div/form/footer/div[1]/div[1]/button/span')
        login_button.click()
        time.sleep(5)
        input("Done logging into Robinhood?")



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
        

        self._save_report(
            order.sym,
            ActionType.BUY,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
            order_id=None,
            quantity=order.quantity,
        )

    def sell(self, order: StockOrder) -> None:
        
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = self._get_current_time()

        res = self._market_sell(order)

        program_executed = datetime.now().strftime("%X:%f")  # when order went through
        post_stock_data = self._get_stock_data(order.sym)


        self._save_report(
            order.sym,
            ActionType.SELL,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
            order_id=None,
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

    def _market_buy(self, order: StockOrder):
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
            self._place_market_order(order, "BUY")
        return
    
    def _market_sell(self, order: StockOrder):
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
            self._place_market_order(order, "SELL")
        return
    
    
    def _place_market_order(self, order: StockOrder, order_type: str):
        # Open Individual Stock Page
        self._chrome_inst.open(f"https://robinhood.com/stocks/{order.sym}?source=search")
        time.sleep(5)


        # Flip to Sell tab if it's a sell order
        if order_type == "SELL":
            sell_tab = self._chrome_inst.find(By.XPATH, '//*[@id="sdp-ticker-symbol-highlight"]/div[1]/form/div[1]/div/div[1]/div/div/div[2]')
            sell_tab.click()
            time.sleep(1)

        # Set to Shares
        set_to_shares_dropdown_elem = self._chrome_inst.find(By.XPATH, '//*[@id="sdp-ticker-symbol-highlight"]/div[1]/form/div[2]/div/div[2]/div/div/div/div/div')
        set_to_shares_dropdown_elem.click()
        time.sleep(1)
        shares_dropdown_elem = self._chrome_inst.find(By.XPATH, "//li[contains(@id, '-options-menu-list-option-share')]")
        shares_dropdown_elem.click()
        time.sleep(1)

        # Enter # of shares
        shares_input_elem = self._chrome_inst.find(By.XPATH, '//*[@id="sdp-ticker-symbol-highlight"]/div[1]/form/div[2]/div/div[3]/div/div/div/div/input')
        self._chrome_inst.sendKeyboardInput(shares_input_elem, order.quantity)
        time.sleep(1)

        # Click Review Order button
        review_order_button = self._chrome_inst.find(By.XPATH, '//*[@id="sdp-ticker-symbol-highlight"]/div[1]/form/div[3]/div/div[2]/div/div/button')
        review_order_button.click()
        time.sleep(3)

        # Click Buy/Sell Button
        final_button = self._chrome_inst.find(By.XPATH, '//*[@id="sdp-ticker-symbol-highlight"]/div[1]/form/div[3]/div/div[2]/div[1]/div/button')
        final_button.click()

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
        # Open Page
        self._chrome_inst.open(f"https://robinhood.com/stocks/{sym}?source=search")
        time.sleep(3)


        # Set to Shares
        set_to_shares_dropdown_elem = self._chrome_inst.find(By.XPATH, '//*[@id="sdp-ticker-symbol-highlight"]/div[1]/form/div[2]/div/div[2]/div/div/div/div/div')
        set_to_shares_dropdown_elem.click()
        time.sleep(1)
        shares_dropdown_elem = self._chrome_inst.find(By.XPATH, "//li[contains(@id, '-options-menu-list-option-share')]")
        shares_dropdown_elem.click()
        time.sleep(1)

        # Click button to open up window w/ data
        set_to_shares_dropdown_elem = self._chrome_inst.find(By.XPATH, "//*[@id='sdp-ticker-symbol-highlight']/div[1]/form/div[2]/div/div[4]//button")
        set_to_shares_dropdown_elem.click()
        time.sleep(1)

        last_sale_data = self._chrome_inst.find(By.XPATH, '//*[@id="equity-order-form-bid-ask-popover"]/div/div/div[3]/div[1]/div[2]/span')
        last_sale_data_text = last_sale_data.text
        price_str, volume_str = last_sale_data_text.split("×")
        last_sale_price = float(price_str.strip().replace("$", ""))
        last_sale_volume = float(volume_str.strip())


        bid_data = self._chrome_inst.find(By.XPATH, '//*[@id="equity-order-form-bid-ask-popover"]/div/div/div[3]/div[2]/div[2]/span')
        bid_data_text = bid_data.text
        price_str, volume_str = bid_data_text.split("×")
        bid_price = float(price_str.strip().replace("$", ""))

        
        ask_data = self._chrome_inst.find(By.XPATH, '//*[@id="equity-order-form-bid-ask-popover"]/div/div/div[3]/div[3]/div[2]/span')
        ask_data_text = ask_data.text
        price_str, volume_str = ask_data_text.split("×")
        ask_price = float(price_str.strip().replace("$", ""))
        
        return StockData(
            ask_price,
            bid_price,
            last_sale_price,
            last_sale_volume,
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
            # by_sms=True,
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
    (for web version, api version is commented out below)
    '''
    def buy_and_sell_immediately(self, symbol):
        
        buy_program_submitted = datetime.now().strftime("%I:%M:%S %p")
        # ask_price = self.get_ask_price_web(symbol)
        # buy_limit_price = round(ask_price * 1.02, 2)
        # self.buy_limit_web(symbol, ask_price)

        # what if we extract the ask / bid while we are buying and selling, so that we save time?
        ask_price, buy_limit_price = self.buy_limit_web(symbol)
        logger.info(f"Bought {symbol} on Robinhood")

        sell_program_submitted = datetime.now().strftime("%I:%M:%S %p")
        # bid_price = self.get_bid_price_web(symbol)
        # sell_limit_price = round(bid_price * 0.98, 2)
        bid_price, sell_limit_price = self.sell_limit_web(symbol)
        logger.info(f"Sold {symbol} on Robinhood")

        self.add_to_24_hour_report_web(
            symbol=symbol, 
            buy_submitted_time=buy_program_submitted, 
            sell_submitted_time=sell_program_submitted, 
            ask_price=ask_price, 
            bid_price=bid_price, 
            buy_limit_price=buy_limit_price, 
            sell_limit_price=sell_limit_price
            )
        
        return




    '''
    Buys and Sells symbol immediately
    Adds to report
    (api version)
    '''
    # def buy_and_sell_immediately(self, symbol):

    #     buy_program_submitted = datetime.now().strftime("%I:%M:%S %p")
    #     ask_price = self.get_ask_price(symbol)
    #     buy_id, buy_limit_price = self.buy_limit(symbol)
    #     logger.info(f"Bought {symbol} on Robinhood")

    #     sell_program_submitted = datetime.now().strftime("%I:%M:%S %p")
    #     bid_price = self.get_bid_price(symbol)
    #     sell_id, sell_limit_price = self.sell_limit(symbol)
    #     logger.info(f"Sold {symbol} on Robinhood")

    #     # add to report somehow here!

    #     try:
    #         buy_program_submitted = datetime.now().strftime("%I:%M:%S %p")
    #         ask_price = self.get_ask_price_web(symbol)
    #         buy_id, buy_limit_price = self.buy_limit(symbol)
    #         logger.info(f"Bought {symbol} on Robinhood")

    #         sell_program_submitted = datetime.now().strftime("%I:%M:%S %p")
    #         bid_price = self.get_bid_price_web(symbol)
    #         sell_id, sell_limit_price = self.sell_limit(symbol)
    #         logger.info(f"Sold {symbol} on Robinhood")
    #     except Exception as e:      # ADD IN THE ACTUAL EXCEPTION THAT HAPPENS WHEN ORDER GETS REJECTED
    #         logger.info("Exception Caught on Robinhood:")
    #         print(e)
    #         ask_price = self.get_ask_price(symbol)
    #         bid_price = self.get_bid_price(symbol)
    #         self.add_rejected_order_to_report(symbol, buy_program_submitted, ask_price, bid_price)
    #         return

    #     try:
    #         self.add_to_24_hour_report(buy_id, sell_id, symbol, buy_program_submitted, sell_program_submitted, ask_price, bid_price, buy_limit_price, sell_limit_price)
    #     except Exception as e:
    #         logger.info("Exception Caught while adding to report on RH")
    #         # likely unable to pull data
    #         # so, add to report but leave price blank

    
    # def buy_and_sell_immediately(self, symbol):

    #     # market_hours_flag = self.get_correct_market_flag()

    #     try:
    #         buy_program_submitted = datetime.now().strftime("%I:%M:%S %p")
    #         ask_price = self.get_ask_price(symbol)
    #         buy_id, buy_limit_price = self.buy_limit(symbol)
    #         logger.info(f"Bought {symbol} on Robinhood")

    #         sell_program_submitted = datetime.now().strftime("%I:%M:%S %p")
    #         bid_price = self.get_bid_price(symbol)
    #         sell_id, sell_limit_price = self.sell_limit(symbol)
    #         logger.info(f"Sold {symbol} on Robinhood")
    #     except Exception as e:      # ADD IN THE ACTUAL EXCEPTION THAT HAPPENS WHEN ORDER GETS REJECTED
    #         logger.info("Exception Caught on Robinhood:")
    #         print(e)
    #         ask_price = self.get_ask_price(symbol)
    #         bid_price = self.get_bid_price(symbol)
    #         self.add_rejected_order_to_report(symbol, buy_program_submitted, ask_price, bid_price)
    #         return

    #     try:
    #         self.add_to_24_hour_report(buy_id, sell_id, symbol, buy_program_submitted, sell_program_submitted, ask_price, bid_price, buy_limit_price, sell_limit_price)
    #     except Exception as e:
    #         logger.info("Exception Caught while adding to report on RH")
    #         # likely unable to pull data
    #         # so, add to report but leave price blank

# =================================================================================================================

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
        extended_afternoon_end = time(17, 0)  # 5:00 PM
        all_day_start = time(17, 0)  # 5:00 PM
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

# =================================================================================================================

    '''
    Buys an extended/after hours limit order using web solution instead of API
    How are we going to handle data collection?
    '''
    # def buy_limit_web(self, symbol, ask_price):
    def buy_limit_web(self, symbol):

        market_hours_flag = self.get_correct_market_flag()
        # limit_price = round(ask_price * 1.02, 2)

        # Open Individual Stock Page
        self._chrome_inst.open(f"https://robinhood.com/stocks/{symbol}?source=search")
        time.sleep(4)

        ask_price, limit_price = self.put_in_order_web(market_hours_flag, "BUY")

        return ask_price, limit_price
    

    '''
    Buys an extended/after hours limit order
    Return order id in order to pull data later
    '''
    def buy_limit(self, symbol):

        market_hours_flag = self.get_correct_market_flag()
        limit_price = round(self.get_ask_price(symbol) * 1.05, 2)
        
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
    

        order_id = res['id']
        # print(res)
        return order_id, limit_price

# =================================================================================================================

    '''
    Sells an extended/after hours limit order using web solution instead of API
    '''
    def sell_limit_web(self, symbol):

        market_hours_flag = self.get_correct_market_flag()
        # limit_price = round(bid_price * 0.98, 2)
        
        # Open Individual Stock Page
        self._chrome_inst.open(f"https://robinhood.com/stocks/{symbol}?source=search")
        time.sleep(4)

        # Flip to Sell tab if it's a sell order
        sell_tab = self._chrome_inst.find(By.XPATH, "//div[@data-testid='OrderFormHeading-Sell']")
        sell_tab.click()
        time.sleep(1)

        bid_price, limit_price = self.put_in_order_web(market_hours_flag, "SELL")

        return bid_price, limit_price
    

    '''
    Sells an extended/after hours limit order
    Return order id in order to pull data later
    '''
    def sell_limit(self, symbol):

        market_hours_flag = self.get_correct_market_flag()
        limit_price = round(self.get_bid_price(symbol) * 0.95, 2)

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
        return order_id, limit_price
    
# =================================================================================================================

    '''
    In our buy/sell functions for web, inputting the data is the same code across both so putting them
    in one function here
    '''
    def put_in_order_web(self, market_hours_flag, action):
        # Open Order type dropdown
        order_type_dropdown = self._chrome_inst.find(By.XPATH, '//*[@id="downshift-1-toggle-button"]')
        order_type_dropdown.click()
        time.sleep(1)
        # input("Done opening dropdown?")


        # Click Limit Order Tab
        limit_order_tab = self._chrome_inst.find(By.XPATH, "//li[.//span[normalize-space()='Limit order']]")
        limit_order_tab.click()
        time.sleep(1)
        # input("Done selecting limit order?")

        # GET ASK/BID AND CALCULATE LIMIT PRICE HERE!!!!
        if action == "BUY":
            ask_price = self.get_ask_price_web()
            limit_price = round(ask_price * 1.02, 2)
        elif action == "SELL":
            bid_price = self.get_bid_price_web()
            limit_price = round(bid_price * 0.98, 2)

        # Enter limit price
        limit_price_tab = self._chrome_inst.find(By.XPATH, "//input[@name='limitPrice']")
        self._chrome_inst.sendKeyboardInput(limit_price_tab, str(limit_price))
        time.sleep(0.5)
        # input("Done inputting limit price?")

        
        # Enter shares
        shares_tab = self._chrome_inst.find(By.XPATH, "//input[@data-testid='OrderFormRows-Shares']")
        self._chrome_inst.sendKeyboardInput(shares_tab, "1")
        time.sleep(0.5)
        # input("Done setting shares")

        # Click trading hours tab
        trading_hours_dropdown = self._chrome_inst.find(By.XPATH, "//button[.//span[normalize-space()='Market Hours']]")
        trading_hours_dropdown.click()
        time.sleep(0.5)
        # input("Dropdown open?")

        # Select proper trading hours
        if market_hours_flag == "extended_hours":
            trading_hours_tab = self._chrome_inst.find(By.XPATH, "//li[@role='option' and .//span[normalize-space()='Extended Hours']]")
            trading_hours_tab.click()
        elif market_hours_flag == "all_day_hours":
            trading_hours_tab = self._chrome_inst.find(By.XPATH, "//li[@role='option' and .//span[normalize-space()='24 Hour Market']]")
            trading_hours_tab.click()
        time.sleep(0.5)
        # input("Correct hours selected?")

        # Click Review Order Button
        review_order_button = self._chrome_inst.find(By.XPATH, "//button[@data-testid='OrderFormControls-Review']")
        review_order_button.click()
        time.sleep(2)
        # input("Review order clicked?")

        # Click buy button to submit order
        buy_button = self._chrome_inst.find(By.XPATH, "//button[@data-testid='OrderFormControls-Submit']")
        buy_button.click()
        time.sleep(1)

        # LAST ERROR WAS AN UNPACKING ERROR RIGHT HERE
        return (ask_price, limit_price) if action == "BUY" else (bid_price, limit_price)
    
# =================================================================================================================

    """
    Adds to 24 hour trade report, but for web version!
    """
    def add_to_24_hour_report_web(self, symbol, buy_submitted_time, sell_submitted_time, ask_price, bid_price, buy_limit_price, sell_limit_price):

        buy_price, buy_executed_time, sell_price, sell_executed_time = self.get_price_and_execution_time_web()

        spread_value = round(float(buy_price) - float(sell_price), 2)

        
        buy_report_entry = TwentyFourReportEntry(
            date=datetime.today().strftime("%m/%d/%Y"),
            program_submitted=buy_submitted_time,
            broker_executed=buy_executed_time,
            sym=symbol,
            broker='RH',
            action="BUY",
            quantity=1,
            price=buy_price,
            spread=spread_value, 
            ask=ask_price,
            bid=bid_price,
            limit_price=buy_limit_price
            )
        
        sell_report_entry = TwentyFourReportEntry(
            date=datetime.today().strftime("%m/%d/%Y"),
            program_submitted=sell_submitted_time,
            broker_executed=sell_executed_time,
            sym=symbol,
            broker='RH',
            action="SELL",
            quantity=1,
            price=sell_price,
            spread=spread_value, 
            ask=ask_price,
            bid=bid_price,
            limit_price=sell_limit_price
            )

        logger.info(f"Added {symbol} to report for RH")

        # write to report file
        date = datetime.now().strftime("%m_%d")
        report_file = BASE_PATH / f"reports/24_hour/24_report_{date}.csv"
        with report_file.open("a") as file:
            file.write(str(buy_report_entry))
            file.write(str(sell_report_entry))

        return
    

    '''
    Scapes the history page on robinhood for price and execution time
    of the last two orders completed, which should be the last buy and 
    sell
    '''
    def get_price_and_execution_time_web(self):
        self._chrome_inst.open(f"https://robinhood.com/account/history")
        time.sleep(4)

        items = self._chrome_inst._driver.find_elements(By.XPATH, "//div[@data-testid='activity-item']")
        sell_price = None
        sell_executed_time = None
        buy_price = None
        buy_executed_time = None

        counter = 0
        for item in items[:2]:
            # expand the item
            item.find_element(
                By.XPATH, ".//button[@data-testid='rh-ExpandableItem-button']"
            ).click()

            time.sleep(1)

            # input("items expanded?")

            title = item.find_element(By.XPATH, ".//h3").text

            price = item.find_element(
                By.XPATH, ".//div[contains(@class,'css-5a1gnn')]//h3"
            ).text
            price = float(price[1:])

            symbol = item.find_element(
                By.XPATH,
                ".//div[@data-testid='cell-label'][.//div[text()='Symbol']]//a"
            ).text

            time_sold = item.find_element(
                By.XPATH,
                ".//span/div[contains(normalize-space(.), ' at ') and (contains(., ' AM') or contains(., ' PM'))]"
            ).text

            # Split by ' at ' to get the part after the date
            print(time_sold)
            time_part = time_sold.split(" at ")[1]  # "3:50 PM PST"
            time_only = " ".join(time_part.split()[:2])

            if counter == 0:
                sell_price = price
                sell_executed_time = time_only
            elif counter == 1:
                buy_price = price
                buy_executed_time = time_only
            counter += 1
        
        print(F"Buy price: {buy_price}, buy time: {buy_executed_time}")
        print(F"Sell price: {sell_price}, sell time: {sell_executed_time}")

        return buy_price, buy_executed_time, sell_price, sell_executed_time
    

    '''
    Adds the buy and sell trades to the report
    '''
    def add_to_24_hour_report(self, buy_id, sell_id, symbol, buy_submitted_time, sell_submitted_time, ask_price, bid_price, buy_limit_price, sell_limit_price):

        # logger.info("About to create entries")
        # get prices, create report entries
        buy_price, buy_report_entry = self.create_24_hour_report_entry(buy_id, symbol, "BUY", buy_submitted_time, ask_price, bid_price, buy_limit_price)
        sell_price, sell_report_entry = self.create_24_hour_report_entry(sell_id, symbol, "SELL", sell_submitted_time, ask_price, bid_price, sell_limit_price)

        # calculate and add spread to report entries
        spread_value =  round(float(buy_price) - float(sell_price), 2)
        buy_report_entry.spread = spread_value
        sell_report_entry.spread = spread_value


        logger.info(f"Added {symbol} to report for RH")
        # print(str(buy_report_entry))

        # write to report file
        date = datetime.now().strftime("%m_%d")
        report_file = BASE_PATH / f"reports/24_hour/24_report_{date}.csv"
        with report_file.open("a") as file:
            file.write(str(buy_report_entry))
            file.write(str(sell_report_entry))

# =================================================================================================================


    '''
    Creates report entry objects
    Requires the trade id in order to pull price and execution time from API

    Returns price so we can calculate spread later and add it to report
    '''
    def create_24_hour_report_entry(self, order_id, symbol, action, submit_time, ask_price, bid_price, limit_price):

        time.sleep(1)
        order_data = rh.get_stock_order_info(order_id)

        # print(order_data)
        # logger.info("Before error points")

        # if can't pull execution data, try again!
        if len(order_data['executions']) == 0:
            time.sleep(2)
            order_data = rh.get_stock_order_info(order_id)
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
                        spread=None, 
                        ask=ask_price,
                        bid=bid_price,
                        limit_price=limit_price
                        )

        return price, report_entry

# =================================================================================================================

    '''
    Adds orders that get rejected to the report
    Sets price + spread to 0 to indicate rejection
    '''
    def add_rejected_order_to_report(self, symbol, submit_time, ask_price, bid_price):
        buy_report_entry = TwentyFourReportEntry(
                            date=datetime.today().strftime("%m/%d/%Y"),
                            program_submitted=submit_time,
                            broker_executed=submit_time,
                            sym=symbol,
                            broker='RH',
                            action="BUY",
                            quantity=1,
                            price=0,
                            spread=0, 
                            ask=ask_price,
                            bid=bid_price,
                            limit_price = round(ask_price * 1.05, 2)
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
                            spread=0,
                            ask=ask_price,
                            bid=bid_price,
                            limit_price = round(bid_price * 0.95, 2)
                            )
        
        # write to report file
        date = datetime.now().strftime("%m_%d")
        report_file = BASE_PATH / f"reports/24_hour/24_report_{date}.csv"
        with report_file.open("a") as file:
            file.write(str(buy_report_entry))
            file.write(str(sell_report_entry))

# =================================================================================================================

    # def get_ask_price_web(self, symbol):
    def get_ask_price_web(self):
        # Open Individual Stock Page
        # self._chrome_inst.open(f"https://robinhood.com/stocks/{symbol}?source=search")
        # time.sleep(4)

        # # Open Order type dropdown
        # order_type_dropdown = self._chrome_inst.find(By.XPATH, '//*[@id="downshift-1-toggle-button"]')
        # order_type_dropdown.click()
        # time.sleep(0.5)

        # # Click Limit Order Tab
        # limit_order_tab = self._chrome_inst.find(By.XPATH, "//li[.//span[normalize-space()='Limit order']]")
        # limit_order_tab.click()
        # time.sleep(0.5)

        # Extract data
        bid_ask_button = self._chrome_inst.find(By.XPATH, "//button[.//span/div/span[contains(text(), 'Bid')]]")
        text = bid_ask_button.text
        numbers = re.findall(r"\$([0-9]+\.[0-9]+)", text)
        bid, ask = numbers  # ['241.60', '242.13']
        
        return float(ask)
    
    def get_ask_price(self, symbol):
        return round(float(rh.stocks.get_quotes(symbol)[0]["ask_price"]), 2)

# =================================================================================================================

    # def get_bid_price_web(self, symbol):
    def get_bid_price_web(self):
        # Open Individual Stock Page
        # self._chrome_inst.open(f"https://robinhood.com/stocks/{symbol}?source=search")
        # time.sleep(4)
        
        # # Open Order type dropdown
        # order_type_dropdown = self._chrome_inst.find(By.XPATH, '//*[@id="downshift-1-toggle-button"]')
        # order_type_dropdown.click()
        # time.sleep(0.5)

        # # Click Limit Order Tab
        # limit_order_tab = self._chrome_inst.find(By.XPATH, "//li[.//span[normalize-space()='Limit order']]")
        # limit_order_tab.click()
        # time.sleep(0.5)

        # Extract data
        bid_ask_button = self._chrome_inst.find(By.XPATH, "//button[.//span/div/span[contains(text(), 'Bid')]]")
        text = bid_ask_button.text
        numbers = re.findall(r"\$([0-9]+\.[0-9]+)", text)
        bid, ask = numbers  # ['241.60', '242.13']
        
        return float(bid)
    
    def get_bid_price(self, symbol):
        return round(float(rh.stocks.get_quotes(symbol)[0]["bid_price"]), 2)

# =================================================================================================================

    def sell_24_hour_leftover_positions(self):
        positions, options = self.get_current_positions()
        positions = [(order.sym,order.quantity) for order in positions]
        # format: [('DYN', 1.0), ('GPC', 1.0), ('YINN', 1.0)]

        # for position in positions:
        #     self.sell(position)

        for position in positions:
            for i in range(int(position[1])):
                self.sell_limit(position[0])
                time.sleep(1)



if __name__ == "__main__":

    rh2 = Robinhood2(Path("temp.csv"), BrokerNames.RH, Path("temp_option.csv"))
    rh2.login()

    # rh2.buy_and_sell_immediately("AMZN")
    # rh2.get_price_and_execution_time_web()

    

    rh2.sell_limit_web("AMZN")

    # rh2.add_to_24_hour_report_web()

    # print(rh2.get_bid_price_web("AMZN"))

    
    # time.sleep(5)
    # rh2.sell_limit_web("GOOG", 329.71)
    # input("Done selling?")
    
    # time.sleep(10)

    # rh2.sell_limit_web("AMZN", 241)

    # print(rh2._get_stock_data("V"))

    # order = StockOrder("SNAP", 1)
    # rh2._place_market_order(order, "BUY")
    # input("Buy order placed?")
    # rh2._place_market_order(order, "SELL")


