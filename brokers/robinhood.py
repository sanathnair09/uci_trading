from datetime import datetime
from pathlib import Path
import time

import robin_stocks.robinhood as rh
from brokers import RH_LOGIN, RH_PASSWORD, RH_LOGIN2, RH_PASSWORD2
from utils.broker import Broker
from utils.misc import repeat_on_fail
from utils.report.report import OptionType, OrderType, StockData, ActionType, BrokerNames


class Robinhood(Broker):

    def _get_order_data(self, orderId: str):
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

        res = self._market_buy(sym, amount)

        program_executed = datetime.now().strftime("%X:%f")  # when order went through
        post_stock_data = self._get_stock_data(sym)

        self._add_report(program_submitted, program_executed, None, sym, ActionType.BUY,
                         amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, res["id"], None)

    def sell(self, sym: str, amount: int):
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")

        res = self._market_sell(sym, amount)
        if 'id' in res:
            program_executed = datetime.now().strftime("%X:%f")  # when order went through
            post_stock_data = self._get_stock_data(sym)

            self._add_report(program_submitted, program_executed, None, sym, ActionType.SELL,
                             amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                             False, res["id"], None)
        elif "detail" in res:
            raise ValueError("PDT Protection")

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return rh.order_buy_limit(sym, amount, limit_price, timeInForce='gfd',
                                  extendedHours=False,
                                  jsonify=True)

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return rh.order_sell_limit(sym, amount, limit_price, timeInForce='gtc',
                                   extendedHours=False,
                                   jsonify=True)

    def _market_buy(self, sym: str, amount: int):
        return rh.order_buy_market(sym, amount, timeInForce="gfd", extendedHours=False,
                                   jsonify=True)

    def _market_sell(self, sym: str, amount: int):
        # for fractional on robinhood they have a method called
        return rh.order_sell_market(sym, amount, timeInForce="gfd", extendedHours=False,
                                    jsonify=True)

    def _get_option_data(self, sym: str, strike: float, expiration: str, optionType: OptionType):
        """
        made a modification in the robin_stocks library to delete the write_spinner function which would cause additional information to be printed out
        """
        optionType = OptionType.CALL.value if optionType == OptionType.CALL else OptionType.PUT.value
        return rh.find_options_by_expiration_and_strike(inputSymbols=sym, expirationDate=expiration, strikePrice=strike, optionType=optionType)[0]

    def _buy_call_option(self, sym: str, strike: float, expiration: str):
        limit_price = round(float(self._get_option_data(
            sym, strike, expiration, OptionType.CALL)["ask_price"]) * 1.05, 2)
        return self._perform_option_trade(ActionType.OPEN, OptionType.CALL, sym, limit_price, strike, expiration)

    def _sell_call_option(self, sym: str, strike: float, expiration: str):
        limit_price = round(float(self._get_option_data(
            sym, strike, expiration, OptionType.CALL)["ask_price"]) * 0.95, 2)
        return self._perform_option_trade(ActionType.CLOSE, OptionType.CALL, sym, limit_price, strike, expiration)

    def _buy_put_option(self, sym: str, strike: float, expiration: str):
        return NotImplementedError
        # return self._perform_option_trade(ActionType.OPEN, OptionType.PUT, sym, limit_price, strike, expiration)

    def _sell_put_option(self, sym: str, strike: float, expiration: str):
        return NotImplementedError
        # return self._perform_option_trade(ActionType.CLOSE, OptionType.PUT, sym, limit_price, strike, expiration)

    def _perform_option_trade(self, action: ActionType, optionType: OptionType, sym: str, limit_price: float, strike: float, expiration: str):
        """
        expiration: "YYYY-MM-DD"
        """
        positionEffect = ActionType.OPEN.value if action == ActionType.OPEN else ActionType.CLOSE.value
        optionType = OptionType.CALL.value if optionType == OptionType.CALL else OptionType.PUT.value
        if action == ActionType.OPEN:
            return rh.order_buy_option_limit(positionEffect=positionEffect,
                                             creditOrDebit="debit", price=limit_price,
                                             symbol=sym, quantity=1, expirationDate=expiration, strike=strike,
                                             optionType=optionType, timeInForce="gfd", jsonify=True)
        else:
            return rh.order_sell_option_limit(positionEffect=positionEffect,
                                              creditOrDebit="credit", price=limit_price,
                                              symbol=sym, quantity=1, expirationDate=expiration, strike=strike,
                                              optionType=optionType, timeInForce="gfd", jsonify=True)

    @repeat_on_fail()
    def _get_stock_data(self, sym: str):
        stock_data = rh.stocks.get_quotes(sym)[0]
        return StockData(stock_data["ask_price"], stock_data["bid_price"],
                         rh.stocks.get_latest_price(sym)[0],
                         rh.stocks.get_fundamentals(sym, info="volume")[0])

    def __init__(self, report_file: Path, broker_name: BrokerNames):
        super().__init__(report_file, broker_name)

    def login(self):
        """
        if changing the login credentials go to your (HOME_DIR)/.tokens and delete the robinhood.pickle file
        :return: None
        """
        Robinhood.login_custom(account="RH2")

    @staticmethod
    def login_custom(account="RH"):
        account = account.upper()
        pickle_file = "1" if account == "RH" else "2"
        username = RH_LOGIN if account == "RH" else RH_LOGIN2
        password = RH_PASSWORD if account == "RH" else RH_PASSWORD2
        time_logged_in = 60 * 60 * 24 * 365
        rh.authentication.login(username=username,
                                password=password,
                                expiresIn=time_logged_in,
                                scope='internal',
                                by_sms=True,
                                pickle_name=pickle_file)

    def get_current_positions(self):
        current_positions = []
        positions = rh.account.build_holdings()
        for sym in positions:
            current_positions.append((sym, float(positions[sym]["quantity"])))
        return current_positions

    def resolve_errors(self):
        return NotImplementedError


if __name__ == '__main__':
    r = Robinhood(Path("temp.csv"), BrokerNames.RH)
    r.login()
    print(r.get_current_positions())
    pass
