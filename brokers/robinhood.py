import time
from datetime import datetime
from pathlib import Path

import robin_stocks.robinhood as rh
from brokers import RH_LOGIN, RH_PASSWORD, RH_LOGIN2, RH_PASSWORD2
from utils.broker import Broker
from utils.misc import repeat_on_fail
from utils.report.report import OrderType, StockData, ActionType, BrokerNames


class Robinhood(Broker):

    def _get_order_data(self, orderId: str):  # TODO: finish implementing
        res = []
        order_data = rh.get_stock_order_info(orderId)
        for execution in order_data["executions"]:
            res.append((
                execution["price"],
                execution["quantity"],
                execution["rounded_notional"],  # dollar amt
                execution["timestamp"],
                execution["id"]
            ))
        return res

    def buy(self, sym: str, amount: int):
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        res = self._market_buy(sym, amount)  # 5% above actual price

        program_executed = datetime.now().strftime("%X:%f")  # when order went through
        post_stock_data = self._get_stock_data(sym)

        self._add_report(program_submitted, program_executed, None, sym, ActionType.BUY,
                         amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, res["id"], None)

    def sell(self, sym: str, amount: int):
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        res = self._market_sell(sym, amount,)  # 5% below actual price
        if 'id' in res:
            program_executed = datetime.now().strftime("%X:%f")  # when order went through
            post_stock_data = self._get_stock_data(sym)

            self._add_report(program_submitted, program_executed, None, sym, ActionType.SELL,
                             amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                             False, res["id"], None)
        elif "detail" in res:
            raise ValueError("PDT Protection")

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return rh.order_buy_limit(sym, amount, limit_price, timeInForce = 'gfd',
                                  extendedHours = False,
                                  jsonify = True)

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return rh.order_sell_limit(sym, amount, limit_price, timeInForce = 'gtc',
                                   extendedHours = False,
                                   jsonify = True)

    def _market_buy(self, sym: str, amount: int):
        return rh.order_buy_market(sym, amount, timeInForce = "gfd", extendedHours = False,
                                   jsonify = True)


    def _market_sell(self, sym: str, amount: int):
        # for fractional on robinhood they have a method called
        return rh.order_sell_market(sym, amount, timeInForce = "gfd", extendedHours = False,
                                   jsonify = True)


    @repeat_on_fail()
    def _get_stock_data(self, sym: str):
        stock_data = rh.stocks.get_quotes(sym)[0]
        return StockData(stock_data["ask_price"], stock_data["bid_price"],
                         rh.stocks.get_latest_price(sym)[0],
                         rh.stocks.get_fundamentals(sym, info = "volume")[0])

    def __init__(self, report_file: Path, broker_name: BrokerNames):
        super().__init__(report_file, broker_name)

    def login(self):
        """
        if changing the login credentials go to your (HOME_DIR)/.tokens and delete the robinhood.pickle file
        :return: None
        """
        Robinhood.login_custom(account = "RH2")

    @staticmethod
    def login_custom(account = "RH"):
        account = account.upper()
        pickle_file = "1" if account == "RH" else "2"
        username = RH_LOGIN if account == "RH" else RH_LOGIN2
        password = RH_PASSWORD if account == "RH" else RH_PASSWORD2
        time_logged_in = 60 * 60 * 24 * 365
        rh.authentication.login(username = username,
                                password = password,
                                expiresIn = time_logged_in,
                                scope = 'internal',
                                by_sms = True,
                                pickle_name = pickle_file)

    def get_current_positions(self):
        current_positions = []
        positions = rh.account.build_holdings()
        for sym in positions:
            current_positions.append((sym, float(positions[sym]["quantity"])))
        return current_positions

    def resolve_errors(self):
        return NotImplementedError


if __name__ == '__main__':
    # r = Robinhood(Path("temp.csv"), BrokerNames.RH)
    pass
