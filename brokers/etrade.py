import time
import warnings
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from random import randint
from typing import Union

import pandas as pd
import pyetrade
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from brokers import ETRADE_CONSUMER_KEY, ETRADE_CONSUMER_SECRET, ETRADE_LOGIN, ETRADE_PASSWORD, \
    ETRADE_ACCOUNT_ID_KEY, BASE_PATH
from brokers import ETRADE2_CONSUMER_KEY, ETRADE2_CONSUMER_SECRET, ETRADE2_LOGIN, ETRADE2_PASSWORD, \
    ETRADE2_ACCOUNT_ID_KEY
from utils.broker import Broker
from utils.misc import repeat_on_fail, save_content_to_file
from utils.report.report import StockData, ActionType, OrderType, BrokerNames
from utils.selenium_helper import CustomChromeInstance


_ETradeOrderInfo = namedtuple("ETradeOrderInfo",
                              ["broker_executed", "quantity", "price", "dollar_amt", "orderId"])


class ETrade(Broker):
    def __init__(self, report_file: Union[Path, str], broker_name: BrokerNames):
        super().__init__(report_file, broker_name)
        self._market = None
        self._orders = None
        self._accounts = None
        if broker_name == BrokerNames.ET:
            self._consumer_key = ETRADE_CONSUMER_KEY
            self._consumer_secret = ETRADE_CONSUMER_SECRET
            self._login = ETRADE_LOGIN
            self._password = ETRADE_PASSWORD
            self._account_id = ETRADE_ACCOUNT_ID_KEY
        else:
            self._consumer_key = ETRADE2_CONSUMER_KEY
            self._consumer_secret = ETRADE2_CONSUMER_SECRET
            self._login = ETRADE2_LOGIN
            self._password = ETRADE2_PASSWORD
            self._account_id = ETRADE2_ACCOUNT_ID_KEY

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
            oauth = pyetrade.ETradeOAuth(self._consumer_key,
                                         self._consumer_secret)
            chrome_inst.get(oauth.get_request_token())
            login_element = WebDriverWait(chrome_inst, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="USER"]'))
            )
            login_element.clear()
            login_element.send_keys(self._login)
            password_element = chrome_inst.find_element(By.XPATH, '//*[@id="password"]')
            password_element.clear()
            password_element.send_keys(self._password)
            time.sleep(1)
            chrome_inst.find_element(By.XPATH, '//*[@id="mfaLogonButton"]').click()
            if self._broker_name == BrokerNames.ET:
                button = WebDriverWait(chrome_inst, 5).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "/html/body/div[2]/div/div[3]/form/input[3]"))
                )
                button.click()
            else:
                button = WebDriverWait(chrome_inst, 5).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "/html/body/div[2]/div/div[2]/form/input[3]"))
                )
                button.click()

            code = WebDriverWait(chrome_inst, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "/html/body/div[2]/div/div/input"))
            )
            tokens = oauth.get_access_token(code.get_attribute("value"))
        except Exception as e:
            print("e", e)
            chrome_inst.quit()
            logger.error("Error logging in automatically. Trying Manually...")
            # print("Error logging in automatically. Trying Manually...")
            oauth = pyetrade.ETradeOAuth(self._consumer_key,
                                         self._consumer_secret)
            print(oauth.get_request_token())  # Use the printed URL
            verifier_code = input("Enter verification code: ")
            tokens = oauth.get_access_token(verifier_code)
        finally:
            self._market = pyetrade.ETradeMarket(
                self._consumer_key,
                self._consumer_secret,
                tokens['oauth_token'],
                tokens['oauth_token_secret'],
                dev = False
            )

            self._orders = pyetrade.ETradeOrder(
                self._consumer_key,
                self._consumer_secret,
                tokens['oauth_token'],
                tokens['oauth_token_secret'],
                dev = False
            )
            self._accounts = pyetrade.ETradeAccounts(
                self._consumer_key,
                self._consumer_secret,
                tokens['oauth_token'],
                tokens['oauth_token_secret'],
                dev = False
            )
            chrome_inst.quit()

    @repeat_on_fail()
    def _get_stock_data(self, sym: str):
        quote = self._market.get_quote([sym], resp_format = 'json')['QuoteResponse']['QuoteData'][0]
        return StockData(float(quote['All']['ask']), float(quote['All']['bid']),
                         float(quote['All']['lastTrade']), float(quote['All']['totalVolume']))

    def get_order_data(self, orderId):
        data = self._orders.list_orders(account_id_key = self._account_id, resp_format = "json",
                                        orderId = str(orderId))
        events = data["OrdersResponse"]["Order"][0]["Events"]["Event"]

        splits_df = pd.DataFrame()
        for event in events:
            if event["name"] == "ORDER_EXECUTED":
                size = event["Instrument"][0]["filledQuantity"]
                price = event["Instrument"][0]["averageExecutionPrice"]
                info = pd.Series({
                    "Broker Executed": event['dateTime'],
                    "Size": size,
                    "Price": price,
                    "Action": event["Instrument"][0]["orderAction"],
                    "Dollar Amt": size * price
                })
                splits_df = pd.concat([splits_df, info.to_frame().T], ignore_index = True)

        return splits_df

    @repeat_on_fail()
    def _get_latest_order(self, orderID) -> _ETradeOrderInfo:
        """
        ETrade API: https://apisb.etrade.com/docs/api/order/api-order-v1.html#/definitions/OrdersResponse
        """
        order_data = \
            self._orders.list_orders(account_id_key = self._account_id, resp_format = "json", orderId = orderID)[
                "OrdersResponse"]["Order"][0]
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

        return _ETradeOrderInfo(order_data["placedTime"], quantity, price, dollar_amt, orderId)

    @repeat_on_fail()
    def buy(self, sym: str, amount: int):
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        ### BUY ###
        orderID = self._market_buy(sym, amount)

        ### POST BUY INFO ###
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(sym)

        order_data = self._get_latest_order(orderID)

        self._add_report(program_submitted, program_executed, order_data.broker_executed, sym,
                         ActionType.BUY, order_data.quantity, order_data.price,
                         order_data.dollar_amt, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, order_data.orderId, None)

    @repeat_on_fail()
    def sell(self, sym: str, amount: int):
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        ### BUY ###
        orderID = self._market_sell(sym, amount)

        ### POST BUY INFO ###
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(sym)

        order_data = self._get_latest_order(orderID)

        self._add_report(program_submitted, program_executed, order_data.broker_executed, sym,
                         ActionType.SELL, order_data.quantity, order_data.price,
                         order_data.dollar_amt, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, order_data.orderId, None)

    def _market_buy(self, sym: str, amount: int):
        res = self._orders.place_equity_order(accountIdKey = self._account_id, symbol = sym,
                                        orderAction = "BUY",
                                        clientOrderId = str(randint(100000, 999999)),
                                        priceType = "MARKET", quantity = amount,
                                        orderTerm = "GOOD_FOR_DAY", marketSession = "REGULAR")

        return res["PlaceOrderResponse"]["OrderIds"]["orderId"]

    def _market_sell(self, sym: str, amount: int):
        res = self._orders.place_equity_order(accountIdKey = self._account_id, symbol = sym,
                                        orderAction = "SELL",
                                        clientOrderId = str(randint(100000, 999999)),
                                        priceType = "MARKET", quantity = amount,
                                        orderTerm = "GOOD_FOR_DAY",
                                        marketSession = "REGULAR")
        return res["PlaceOrderResponse"]["OrderIds"]["orderId"]

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def get_current_positions(self):
        current_positions = []
        # try catch for when nothing left
        positions = self._accounts.get_account_portfolio(self._account_id)["PortfolioResponse"][
            "AccountPortfolio"]["Position"]
        if type(positions) is list:  # multiple stocks are left over
            for position in positions:
                current_positions.append((position["symbolDescription"], position["quantity"]))
        else:
            current_positions.append((positions["symbolDescription"], positions["quantity"]))

        return current_positions


if __name__ == '__main__':
    et = ETrade(Path("temp.csv"), BrokerNames.E2)
    et.login()
    pos = et.get_current_positions()
    print(pos)