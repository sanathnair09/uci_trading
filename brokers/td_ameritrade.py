from datetime import datetime, timedelta
from pathlib import Path

import tda.auth
from loguru import logger
from tda.orders.equities import equity_buy_market, equity_sell_market

from utils.broker import Broker
from brokers import TD_KEY, TD_URI, TD_TOKEN_PATH, TD_ACC_NUM
from utils.selenium_helper import CustomChromeInstance
from utils.misc import repeat_on_fail, calculate_num_stocks_to_buy
from utils.report.report import StockData, ActionType, OrderType, BrokerNames


class TDAmeritrade(Broker):
    def __init__(self, report_file: Path, broker_name: BrokerNames):
        super().__init__(report_file, broker_name)
        self._driver = CustomChromeInstance.createInstance()
        self._client: tda.client.Client = None

    @staticmethod
    def validate_stock(sym: str):
        client = tda.auth.client_from_token_file(TD_TOKEN_PATH, TD_KEY)
        res = client.get_quotes(sym).json()
        valid = sym in res and res[sym]["description"] != "Symbol not found"
        if not valid:
            logger.error(f"{sym} not valid")
        return valid

    @staticmethod
    def get_stock_amount(sym: str) -> tuple[int, float]:
        client = tda.auth.client_from_token_file(TD_TOKEN_PATH, TD_KEY)
        price = client.get_quotes(sym).json()[sym]['lastPrice']
        return calculate_num_stocks_to_buy(100, price), price

    @staticmethod
    def get_stock_data(sym: str) -> StockData:
        client = tda.auth.client_from_token_file(TD_TOKEN_PATH, TD_KEY)  # Path.cwd().parent /
        stock_data = client.get_quotes(sym).json()[sym]
        return StockData(stock_data["askPrice"], stock_data["bidPrice"],
                         stock_data["lastPrice"], stock_data["totalVolume"])

    def login(self):
        try:
            self._client = tda.auth.client_from_token_file(TD_TOKEN_PATH, TD_KEY)
        except:  # if the token is expired or some other issue try logging in using a browser
            print("Issue logging in with token trying manual...")
            self._client = tda.auth.client_from_login_flow(self._driver, TD_KEY, TD_URI,
                                                           TD_TOKEN_PATH)

    @repeat_on_fail()
    def _get_stock_data(self, sym: str) -> StockData:
        stock_data = self._client.get_quotes(sym).json()[sym]
        return StockData(stock_data["askPrice"], stock_data["bidPrice"],
                         stock_data["lastPrice"], stock_data["totalVolume"])

    def _get_latest_order(self):
        return self._client.get_orders_by_path(TD_ACC_NUM,
                                               from_entered_datetime = datetime.now(),
                                               to_entered_datetime = datetime.now() + timedelta(
                                                   1)).json()[0]

    def buy(self, sym: str, amount: int):
        ### PRE BUY INFO ###
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        ### BUY ###
        self._market_buy(sym, amount)

        ### POST BUY INFO ###
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(sym)

        order_data = self._get_latest_order()

        for activity in order_data["orderActivityCollection"]:
            TD_ct = activity['executionLegs'][0]['time'][11:]
            TD_ct_hour = str(int(TD_ct[:2]) - 7)
            if len(TD_ct_hour) == 1:
                TD_ct_hour = "0" + TD_ct_hour
            broker_executed = TD_ct_hour + TD_ct[2:-5]

            self._add_report(program_submitted, program_executed, broker_executed, sym,
                             ActionType.BUY,
                             activity["quantity"], activity["executionLegs"][0]['price'],
                             activity["quantity"] * activity["executionLegs"][0]['price'],
                             pre_stock_data, post_stock_data, OrderType.MARKET,
                             len(order_data["orderActivityCollection"]) > 1, order_data["orderId"],
                             order_data["orderActivityCollection"][0]["activityId"])

    def sell(self, sym: str, amount: int):
        ### PRE BUY INFO ###
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        ### BUY ###
        self._market_sell(sym, amount)

        ### POST BUY INFO ###
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(sym)

        order_data = self._get_latest_order()

        for activity in order_data["orderActivityCollection"]:
            TD_ct = activity['executionLegs'][0]['time'][11:]
            TD_ct_hour = str(int(TD_ct[:2]) - 7)
            if len(TD_ct_hour) == 1:
                TD_ct_hour = "0" + TD_ct_hour
            broker_executed = TD_ct_hour + TD_ct[2:-5]

            self._add_report(program_submitted, program_executed, broker_executed, sym,
                             ActionType.SELL,
                             activity["quantity"], activity["executionLegs"][0]['price'],
                             activity["quantity"] * activity["executionLegs"][0]['price'],
                             pre_stock_data, post_stock_data, OrderType.MARKET,
                             len(order_data["orderActivityCollection"]) > 1, order_data["orderId"],
                             order_data["orderActivityCollection"][0]["activityId"])

    def _market_buy(self, sym: str, amount: int):
        self._client.place_order(TD_ACC_NUM, equity_buy_market(sym, amount).build())

    def _market_sell(self, sym: str, amount: int):
        self._client.place_order(TD_ACC_NUM, equity_sell_market(sym, amount).build())

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def get_current_positions(self):
        positions = self._client.get_account(TD_ACC_NUM, fields = [
            tda.client.Client.Account.Fields.POSITIONS]
                                             ).json()['securitiesAccount']["positions"]
        current_positions = []
        for position in positions:
            current_positions.append((position["instrument"]["symbol"], position["longQuantity"]))

        return current_positions

    def resolve_errors(self):
        return NotImplementedError


if __name__ == '__main__':
    # td = TDAmeritrade(Path("temp.csv"), BrokerNames.TD)
    pass