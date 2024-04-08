from collections import namedtuple
from datetime import datetime
from pathlib import Path
from pyexpat import ExpatError
from random import randint
from typing import Optional, Union

import pandas as pd
import pyetrade
from loguru import logger

from brokers import (
    ETRADE2_CONSUMER_KEY,
    ETRADE2_CONSUMER_SECRET,
    ETRADE2_LOGIN,
    ETRADE2_PASSWORD,
    ETRADE2_ACCOUNT_ID_KEY,
)
from brokers import (
    ETRADE_CONSUMER_KEY,
    ETRADE_CONSUMER_SECRET,
    ETRADE_LOGIN,
    ETRADE_PASSWORD,
    ETRADE_ACCOUNT_ID_KEY,
)
from utils.broker import Broker, OptionOrder, StockOrder
from utils.report.report import (
    NULL_OPTION_DATA,
    OptionReportEntry,
    OptionType,
    ReportEntry,
    StockData,
    ActionType,
    OrderType,
    BrokerNames,
    OptionData,
)
from utils.selenium_helper import CustomChromeInstance
from utils.util import repeat_on_fail


_ETradeOrderInfo = namedtuple(
    "ETradeOrderInfo", ["broker_executed", "quantity", "price", "dollar_amt", "orderId"]
)


class ETrade(Broker):
    def __init__(
        self,
        report_file: Union[Path, str],
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        super().__init__(report_file, broker_name, option_report_file)
        self._broker_name = broker_name
        self._consumer_key = (
            ETRADE_CONSUMER_KEY
            if broker_name == BrokerNames.ET
            else ETRADE2_CONSUMER_KEY
        )
        self._consumer_secret = (
            ETRADE_CONSUMER_SECRET
            if broker_name == BrokerNames.ET
            else ETRADE2_CONSUMER_SECRET
        )
        self._login = ETRADE_LOGIN if broker_name == BrokerNames.ET else ETRADE2_LOGIN
        self._password = (
            ETRADE_PASSWORD if broker_name == BrokerNames.ET else ETRADE2_PASSWORD
        )
        self._account_id = (
            ETRADE_ACCOUNT_ID_KEY
            if broker_name == BrokerNames.ET
            else ETRADE2_ACCOUNT_ID_KEY
        )

    def login(self):
        """
        Possible instability with automated token collection.
        Sometimes the XPATH for line 54 changes so if you notice that it is asking you to manually verify
        add an input statement on line 53 and then check the XPATH and change if needed.
        :return:
        """
        chrome_inst = CustomChromeInstance.createInstance()
        tokens = {}
        try:
            oauth = pyetrade.ETradeOAuth(self._consumer_key, self._consumer_secret)
            print(oauth.get_request_token())  # Use the printed URL
            verifier_code = input("Enter verification code: ")
            tokens = oauth.get_access_token(verifier_code)
            # chrome_inst.get(oauth.get_request_token())
            # login_element = WebDriverWait(chrome_inst, 5).until(
            #     EC.presence_of_element_located((By.XPATH, '//*[@id="USER"]'))
            # )
            # login_element.clear()
            # login_element.send_keys(self._login)
            # password_element = chrome_inst.find_element(By.XPATH, '//*[@id="password"]')
            # password_element.clear()
            # password_element.send_keys(self._password)
            # time.sleep(1)
            # chrome_inst.find_element(By.XPATH, '//*[@id="mfaLogonButton"]').click()
            # time.sleep(2)
            # accept = chrome_inst.find_element(By.XPATH, '//*[@id="acceptSubmit"]')
            # accept.click()

            # code = WebDriverWait(chrome_inst, 5).until(
            #     EC.presence_of_element_located(
            #         (By.XPATH, "/html/body/div[2]/div/div/input")
            #     )
            # )
            # tokens = oauth.get_access_token(code.get_attribute("value"))
        except Exception as e:
            chrome_inst.quit()
            logger.error("Error logging in automatically. Trying Manually...")
            # print("Error logging in automatically. Trying Manually...")
            oauth = pyetrade.ETradeOAuth(self._consumer_key, self._consumer_secret)
            print(oauth.get_request_token())  # Use the printed URL
            verifier_code = input("Enter verification code: ")
            tokens = oauth.get_access_token(verifier_code)
        finally:
            self._market = pyetrade.ETradeMarket(
                self._consumer_key,
                self._consumer_secret,
                tokens["oauth_token"],
                tokens["oauth_token_secret"],
                dev=False,
            )

            self._orders = pyetrade.ETradeOrder(
                self._consumer_key,
                self._consumer_secret,
                tokens["oauth_token"],
                tokens["oauth_token_secret"],
                dev=False,
            )
            self._accounts = pyetrade.ETradeAccounts(
                self._consumer_key,
                self._consumer_secret,
                tokens["oauth_token"],
                tokens["oauth_token_secret"],
                dev=False,
            )
            chrome_inst.quit()

    def _get_stock_data(self, sym: str):
        quote = self._market.get_quote([sym], resp_format="json")["QuoteResponse"][
            "QuoteData"
        ][0]
        return StockData(
            float(quote["All"]["ask"]),
            float(quote["All"]["bid"]),
            float(quote["All"]["lastTrade"]),
            float(quote["All"]["totalVolume"]),
        )

    def get_order_data(self, orderId, sym: str, date: str):
        date_object = datetime.strptime(date, r"%m/%d/%y")
        fromDate = date_object.strftime(r"%m%d%Y")
        data = self._orders.list_orders(
            account_id_key=self._account_id,  # type: ignore
            resp_format="json",
            orderId=str(orderId),
            symbol=sym,
            fromDate=fromDate,
            toDate=fromDate,
        )
        events = data["OrdersResponse"]["Order"][0]["Events"]["Event"]

        splits_df = pd.DataFrame()
        for event in events:
            if event["name"] == "ORDER_EXECUTED":
                size = event["Instrument"][0]["filledQuantity"]
                price = event["Instrument"][0]["averageExecutionPrice"]
                info = pd.Series(
                    {
                        "Broker Executed": event["dateTime"],
                        "Size": size,
                        "Price": price,
                        "Action": event["Instrument"][0]["orderAction"],
                        "Dollar Amt": size * price,
                    }
                )
                splits_df = pd.concat([splits_df, info.to_frame().T], ignore_index=True)

        return splits_df, (splits_df.shape[0] > 1)

    def get_order_option_data(self, orderId, sym: str, date: str):
        date_object = datetime.strptime(date, r"%m/%d/%y")
        fromDate = date_object.strftime(r"%m%d%Y")
        data = self._orders.list_orders(
            account_id_key=self._account_id,  # type: ignore
            resp_format="json",
            orderId=str(orderId),
            symbol=sym,
            fromDate=fromDate,
            toDate=fromDate,
        )
        events = data["OrdersResponse"]["Order"][0]["Events"]["Event"]

        splits_df = pd.DataFrame()
        for event in events:
            if event["name"] == "ORDER_EXECUTED":
                size = event["Instrument"][0]["filledQuantity"]
                price = event["Instrument"][0]["averageExecutionPrice"]
                info = pd.Series(
                    {
                        "Broker Executed": event["dateTime"],
                        "Size": size,
                        "Price": price,
                        "Action": event["Instrument"][0]["orderAction"],
                        "Dollar Amt": size + price * 100,
                    }
                )
                splits_df = pd.concat([splits_df, info.to_frame().T], ignore_index=True)

        return splits_df, (splits_df.shape[0] > 1)

    @repeat_on_fail()
    def _get_latest_order(self, orderID) -> _ETradeOrderInfo:
        """
        ETrade API: https://apisb.etrade.com/docs/api/order/api-order-v1.html#/definitions/OrdersResponse
        """
        order_data = self._orders.list_orders(
            account_id_key=self._account_id, resp_format="json", orderId=orderID  # type: ignore
        )["OrdersResponse"]["Order"][0]
        orderId = order_data["orderId"]
        order_data = order_data["OrderDetail"][0]
        quantity = order_data["Instrument"][0]["orderedQuantity"]
        # averageExecutionPrice key won't exist right after order since order will be OPEN not EXECUTED
        if order_data["status"] == "EXECUTED":
            price = order_data["Instrument"][0]["averageExecutionPrice"]
            dollar_amt = quantity * price
        else:
            price = ""
            dollar_amt = ""

        return _ETradeOrderInfo(
            order_data["placedTime"], quantity, price, dollar_amt, orderId
        )

    def buy(self, order: StockOrder):
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = datetime.now().strftime("%X:%f")

        ### BUY ###
        orderID = self._market_buy(order)

        ### POST BUY INFO ###
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(order.sym)

        self._save_report(
            order.sym,
            ActionType.BUY,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
            orderID=orderID,
        )

    def sell(self, order: StockOrder):
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = datetime.now().strftime("%X:%f")

        ### SELL ###
        orderID = self._market_sell(order)

        ### POST SELL INFO ###
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(order.sym)

        self._save_report(
            order.sym,
            ActionType.SELL,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
            orderID=orderID,
        )

    def buy_option(self, order: OptionOrder):
        ### PRE BUY INFO ###
        pre_stock_data = self._get_option_data(order)
        program_submitted = self._get_current_time()

        ### BUY ###
        if order.option_type == OptionType.CALL:
            orderID = self._buy_call_option(order)
        else:
            orderID = self._buy_put_option(order)

        ### POST BUY INFO ###
        program_executed = self._get_current_time()
        post_stock_data = self._get_option_data(order)

        self._save_option_report(
            order,
            ActionType.BUY,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
            orderID=orderID,
        )

    def sell_option(self, order: OptionOrder):
        ### PRE SELL INFO ###
        pre_stock_data = self._get_option_data(order)
        program_submitted = self._get_current_time()

        ### SELL ###
        if order.option_type == OptionType.CALL:
            orderID = self._sell_call_option(order)
        else:
            orderID = self._sell_put_option(order)

        ### POST BUY INFO ###
        program_executed = self._get_current_time()
        post_stock_data = self._get_option_data(order)

        self._save_option_report(
            order,
            ActionType.SELL,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
            orderID=orderID,
        )

    def _market_buy(self, order: StockOrder):
        return self._order_stock_helper(order, ActionType.BUY, OrderType.MARKET)

    def _market_sell(self, order: StockOrder):
        return self._order_stock_helper(order, ActionType.SELL, OrderType.MARKET)

    def _limit_buy(self, order: StockOrder):
        return NotImplementedError

    def _limit_sell(self, order: StockOrder):
        return NotImplementedError

    def _order_stock_helper(
        self, order: StockOrder, action_type: ActionType, order_type: OrderType
    ):
        # TODO: implement LIMIT orders
        order_action = "BUY" if action_type == ActionType.BUY else "SELL"
        res = self._orders.place_equity_order(
            accountIdKey=self._account_id,
            symbol=order.sym,
            orderAction=order_action,
            clientOrderId=str(randint(100000, 999999)),
            priceType="MARKET",
            quantity=int(order.quantity),
            orderTerm="GOOD_FOR_DAY",
            marketSession="REGULAR",
        )
        return res["PlaceOrderResponse"]["OrderIds"]["orderId"]

    def _buy_call_option(self, order: OptionOrder):
        return self._option_helper(order, ActionType.OPEN)

    def _sell_call_option(self, order: OptionOrder):
        return self._option_helper(order, ActionType.CLOSE)

    def _buy_put_option(self, order: OptionOrder):
        return self._option_helper(order, ActionType.OPEN)

    def _sell_put_option(self, order: OptionOrder):
        return self._option_helper(order, ActionType.CLOSE)

    def _option_helper(self, order: OptionOrder, action_type: ActionType):
        order_action = "BUY_OPEN" if action_type == ActionType.OPEN else "SELL_CLOSE"
        call_put = "CALL" if order.option_type == OptionType.CALL else "PUT"
        res = self._orders.place_option_order(
            accountIdKey=self._account_id,
            symbol=order.sym,
            strikePrice=float(order.strike),
            orderAction=order_action,
            callPut=call_put,
            expiryDate=order.expiration,
            clientOrderId=str(randint(100000, 999999)),
            priceType="MARKET",
            quantity=1,
            orderTerm="GOOD_FOR_DAY",
            marketSession="REGULAR",
        )
        return res["PlaceOrderResponse"]["OrderIds"]["orderId"]

    def _get_option_data(self, option: OptionOrder) -> OptionData:
        date = datetime.strptime(option.expiration, "%Y-%m-%d")
        res = self._market.get_option_chains(
            underlier=option.sym,
            expiry_date=date,
            chain_type=option.option_type.value,
            strike_price_near=float(option.strike),
        )
        data = res["OptionChainResponse"]["OptionPair"]
        for pair in data:
            pair = (
                pair["Call"] if option.option_type == OptionType.CALL else pair["Put"]
            )
            if pair["strikePrice"] == str(option.strike):
                return OptionData(
                    pair["ask"],
                    pair["bid"],
                    pair["lastPrice"],
                    pair["volume"],
                    pair["OptionGreeks"]["iv"],
                    pair["OptionGreeks"]["delta"],
                    pair["OptionGreeks"]["theta"],
                    pair["OptionGreeks"]["gamma"],
                    pair["OptionGreeks"]["vega"],
                    pair["OptionGreeks"]["rho"],
                    "",  # type: ignore # (etrade doesn't provide underlying price)
                    pair["inTheMoney"] == "y",
                )
        return NULL_OPTION_DATA

    def _save_report(
        self,
        sym: str,
        action_type: ActionType,
        program_submitted,
        program_executed,
        pre_stock_data: StockData,
        post_stock_data: StockData,
        **kwargs,
    ):
        order_data = self._get_latest_order(kwargs["orderID"])

        self._add_report_to_file(
            ReportEntry(
                program_submitted,
                program_executed,
                order_data.broker_executed,
                sym,
                action_type,
                order_data.quantity,
                order_data.price,
                order_data.dollar_amt,
                pre_stock_data,
                post_stock_data,
                OrderType.MARKET,
                False,
                order_data.orderId,
                "",  # type: ignore # (etrade doesn't have activity id)
                self._broker_name,
            )
        )

        self._save_report_to_file()

    def _save_option_report(
        self,
        order: OptionOrder,
        action_type: ActionType,
        program_submitted,
        program_executed,
        pre_stock_data: OptionData,
        post_stock_data: OptionData,
        **kwargs,
    ):
        order_data = self._get_latest_order(kwargs["orderID"])

        self._add_option_report_to_file(
            OptionReportEntry(
                program_submitted,
                program_executed,
                order_data.broker_executed,
                order.sym,
                order.strike,
                order.option_type,
                order.expiration,
                action_type,
                order_data.price,
                pre_stock_data,
                post_stock_data,
                OrderType.MARKET,
                "",
                order_data.orderId,
                "",  # type: ignore # (etrade doesn't have activity id)
                self._broker_name,
            )
        )

        self._save_option_report_to_file()

    def get_current_positions(self):
        current_positions = []
        current_options_positions = []
        # try catch for when nothing left
        try:
            positions = self._accounts.get_account_portfolio(self._account_id)["PortfolioResponse"]["AccountPortfolio"]["Position"]  # type: ignore
            if type(positions) is list:  # multiple stocks are left over
                for position in positions:
                    if position["Product"]["securityType"] == "EQ":
                        current_positions.append(
                            (position["symbolDescription"], position["quantity"])
                        )
                    else:
                        option_type = (
                            OptionType.CALL
                            if position["Product"]["callPut"] == "CALL"
                            else OptionType.PUT
                        )
                        expiration = f'{position["Product"]["expiryYear"]}-{position["Product"]["expiryMonth"]}-{position["Product"]["expiryDay"]}'
                        strike = position["Product"]["strikePrice"]
                        current_options_positions.append(
                            OptionOrder(
                                position["Product"]["symbol"],
                                OrderType.MARKET,
                                option_type,
                                strike,
                                expiration,
                            )
                        )

            else:
                if positions["Product"]["securityType"] == "EQ":
                    current_positions.append(
                        (positions["symbolDescription"], positions["quantity"])
                    )
                else:
                    option_type = (
                        OptionType.CALL
                        if positions["Product"]["callPut"] == "CALL"
                        else OptionType.PUT
                    )
                    month = datetime.strptime(
                        positions["Product"]["expiryMonth"], "%m"
                    ).strftime("%m")
                    expiration = f'{positions["Product"]["expiryYear"]}-{month}-{positions["Product"]["expiryDay"]}'
                    strike = positions["Product"]["strikePrice"]
                    current_options_positions.append(
                        OptionOrder(
                            positions["Product"]["symbol"],
                            OrderType.MARKET,
                            option_type,
                            strike,
                            expiration,
                        )
                    )
        except ExpatError as e:
            pass

        return current_positions, current_options_positions


if __name__ == "__main__":
    et = ETrade(Path("temp.csv"), BrokerNames.E2, Path("temp_option.csv"))
    et.login()
    print(et.get_current_positions())
    pass
