import time
from datetime import datetime
from pathlib import Path

import robin_stocks.robinhood as rh
from brokers import RH_LOGIN, RH_PASSWORD
from utils.broker import Broker
from utils.misc import repeat_on_fail
from utils.report import OrderType, StockData, ActionType, BrokerNames


class Robinhood(Broker):

    def _get_order_data(self, orderId: str): # TODO: finish implementing
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
        date = datetime.now().strftime('%x')
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        res = self._limit_buy(sym, amount,
                              round(float(pre_stock_data.ask) * 1.05, 2))  # 5% above actual price

        program_executed = datetime.now().strftime("%X:%f")  # when order went through
        post_stock_data = self._get_stock_data(sym)

        self._add_report(date, program_submitted, program_executed, None, sym, ActionType.BUY,
                         None, None, None, pre_stock_data, post_stock_data, OrderType.LIMIT,
                         False, res["id"], None, BrokerNames.RH)

    def sell(self, sym: str, amount: int):
        date = datetime.now().strftime('%x')
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        res = self._limit_sell(sym, amount,
                               round(float(pre_stock_data.ask) * 0.95, 2))  # 5% below actual price

        program_executed = datetime.now().strftime("%X:%f")  # when order went through
        post_stock_data = self._get_stock_data(sym)

        self._add_report(date, program_submitted, program_executed, None, sym, ActionType.SELL,
                         None, None, None, pre_stock_data, post_stock_data, OrderType.LIMIT,
                         False, res["id"], None, BrokerNames.RH)

    def _market_buy(self, sym: str, amount: int):
        return NotImplementedError

    def _market_sell(self, sym: str, amount: int):
        return NotImplementedError

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return rh.order_buy_limit(sym, amount, limit_price, timeInForce = 'gfd',
                                  extendedHours = False,
                                  jsonify = True)

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return rh.order_sell_limit(sym, amount, limit_price, timeInForce = 'gtc',
                                   extendedHours = False,
                                   jsonify = True)

    @repeat_on_fail()
    def _get_stock_data(self, sym: str):
        stock_data = rh.stocks.get_quotes(sym)[0]
        return StockData(stock_data["ask_price"], stock_data["bid_price"],
                         rh.stocks.get_latest_price(sym)[0],
                         rh.stocks.get_fundamentals(sym, info = "volume")[0])

    def __init__(self, report_file: Path):
        super().__init__(report_file)

    def login(self):
        time_logged_in = 60 * 60 * 24 * 365
        rh.authentication.login(username = RH_LOGIN,
                                password = RH_PASSWORD,
                                expiresIn = time_logged_in,
                                scope = 'internal',
                                by_sms = True,
                                store_session = True)


if __name__ == '__main__':
    r = Robinhood(Path("temp.csv"))
    r.login()
    r.buy("VRM", 1)
    time.sleep(5)
    r.sell("VRM", 1)
    r.save_report()
    # print(r._executed_trades)
