import time
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from random import randint

import pyetrade
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from brokers import ETRADE_CONSUMER_KEY, ETRADE_CONSUMER_SECRET, ETRADE_LOGIN, ETRADE_PASSWORD, \
    ETRADE_ACCOUNT_ID
from utils.broker import Broker
from utils.misc import repeat_on_fail
from utils.report import StockData, ActionType, OrderType, BrokerNames
from utils.selenium_helper import CustomChromeInstance


_ETradeOrderInfo = namedtuple("ETradeOrderInfo",
                              ["broker_executed", "quantity", "price", "dollar_amt", "orderId"])


class ETrade(Broker):
    def __init__(self, report_file: Path):
        super().__init__(report_file)
        self._market = None
        self._orders = None

    def login(self):
        chrome_inst = CustomChromeInstance.createInstance()
        tokens = {}
        try:
            oauth = pyetrade.ETradeOAuth(ETRADE_CONSUMER_KEY,
                                         ETRADE_CONSUMER_SECRET)
            chrome_inst.get(oauth.get_request_token())
            login_element = WebDriverWait(chrome_inst, 5).until(
                EC.presence_of_element_located(
                    (By.ID, "user_orig"))
            )
            login_element.clear()
            login_element.send_keys(ETRADE_LOGIN)
            password_element = chrome_inst.find_element(By.ID, "PASSWORD")
            password_element.clear()
            password_element.send_keys(ETRADE_PASSWORD)
            time.sleep(1)
            chrome_inst.find_element(By.ID, "logon_button").click()
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
        except:
            chrome_inst.quit()
            print("Error logging in automatically. Trying Manually...")
            oauth = pyetrade.ETradeOAuth(ETRADE_CONSUMER_KEY,
                                         ETRADE_CONSUMER_SECRET)
            print(oauth.get_request_token())  # Use the printed URL
            verifier_code = input("Enter verification code: ")
            tokens = oauth.get_access_token(verifier_code)
        finally:
            self._market = pyetrade.ETradeMarket(
                ETRADE_CONSUMER_KEY,
                ETRADE_CONSUMER_SECRET,
                tokens['oauth_token'],
                tokens['oauth_token_secret'],
                dev = False
            )

            self._orders = pyetrade.ETradeOrder(
                ETRADE_CONSUMER_KEY,
                ETRADE_CONSUMER_SECRET,
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

    def _get_latest_order(self) -> _ETradeOrderInfo:
        """
        ETrade API: https://apisb.etrade.com/docs/api/order/api-order-v1.html#/definitions/OrdersResponse
        """
        order_data = \
            self._orders.list_orders(account_id_key = ETRADE_ACCOUNT_ID, resp_format = "json")[
                "OrdersResponse"]["Order"][0]
        orderId = order_data["orderId"]
        order_data = order_data["OrderDetail"][0]
        quantity = order_data["Instrument"][0]["orderedQuantity"]
        price = order_data["orderValue"] / quantity
        dollar_amt = quantity * price
        return _ETradeOrderInfo(order_data["placedTime"], quantity, price, dollar_amt, orderId)

    def buy(self, sym: str, amount: int):
        date = datetime.now().strftime('%x')
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        ### BUY ###
        self._market_buy(sym, amount)

        ### POST BUY INFO ###
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(sym)

        order_data = self._get_latest_order()

        self._add_report(date, program_submitted, program_executed, order_data.broker_executed, sym,
                         ActionType.BUY, order_data.quantity, order_data.price,
                         order_data.dollar_amt, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, order_data.orderId, None, BrokerNames.ET)

    def sell(self, sym: str, amount: int):
        date = datetime.now().strftime('%x')
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        ### BUY ###
        self._market_sell(sym, amount)

        ### POST BUY INFO ###
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(sym)

        order_data = self._get_latest_order()

        self._add_report(date, program_submitted, program_executed, order_data.broker_executed, sym,
                         ActionType.SELL, order_data.quantity, order_data.price,
                         order_data.dollar_amt, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, order_data.orderId, None, BrokerNames.ET)

    def _market_buy(self, sym: str, amount: int):
        self._orders.place_equity_order(accountIdKey = ETRADE_ACCOUNT_ID, symbol = sym,
                                        orderAction = "BUY",
                                        clientOrderId = str(randint(100000, 999999)),
                                        priceType = "MARKET", quantity = amount,
                                        orderTerm = "GOOD_FOR_DAY", marketSession = "REGULAR")

    def _market_sell(self, sym: str, amount: int):
        self._orders.place_equity_order(accountIdKey = ETRADE_ACCOUNT_ID, symbol = sym,
                                        orderAction = "SELL",
                                        clientOrderId = str(randint(100000, 999999)),
                                        priceType = "MARKET", quantity = amount,
                                        orderTerm = "GOOD_FOR_DAY",
                                        marketSession = "REGULAR")

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    


if __name__ == '__main__':
    e = ETrade(Path("temp.csv"))
    e.login()
    e.buy("GRWG", 1)
    time.sleep(5)
    e.sell("GRWG", 1)
    e.save_report()
    # e.sell("VRM", 1)
    # print(e._executed_trades)
