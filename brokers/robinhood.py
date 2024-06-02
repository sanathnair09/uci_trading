from datetime import datetime
import math
from pathlib import Path
import time
from typing import Any, Optional, Union, cast

import robin_stocks.robinhood as rh  # type: ignore [import-untyped]

from brokers import RH_LOGIN, RH_PASSWORD, RH_LOGIN2, RH_PASSWORD2
from utils.broker import Broker, StockOrder, OptionOrder
from utils.report.report import (
    OptionReportEntry,
    OptionType,
    OrderType,
    ReportEntry,
    StockData,
    ActionType,
    BrokerNames,
    OptionData,
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
            order_id=res["id"],
            quantity=order.quantity,
        )

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
        **kwargs: Union[float, str]
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
        **kwargs: str
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
        Robinhood.login_custom(account="RH2")

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


if __name__ == "__main__":
    r = Robinhood(Path("temp.csv"), BrokerNames.RH, Path("temp_option.csv"))
    r.login()
    pass
