from datetime import datetime, timedelta
from pathlib import Path
import time
from typing import Any, Optional, Union, cast

from loguru import logger
import tda.auth  # type: ignore[import-untyped]
from tda.orders.equities import equity_buy_market, equity_sell_market  # type: ignore[import-untyped]
from tda.orders.options import (  # type: ignore[import-untyped]
    option_buy_to_open_market,
    option_sell_to_close_market,
    OptionSymbol,
)

from brokers import TD_ACC_NUM, TD_KEY, TD_TOKEN_PATH, TD_URI
from utils.broker import Broker, OptionOrder, StockOrder
from utils.market_data import MarketData
from utils.report.report import (
    ActionType,
    BrokerNames,
    OptionData,
    OptionReportEntry,
    OptionType,
    OrderType,
    ReportEntry,
    StockData,
)
from utils.selenium_helper import CustomChromeInstance
from utils.util import parse_option_string


class TDAmeritrade(Broker):
    def __init__(
        self,
        report_file: Path,
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        super().__init__(report_file, broker_name, option_report_file)

    def login(self) -> None:
        try:
            self._client = tda.auth.client_from_token_file(TD_TOKEN_PATH, TD_KEY)
        except:  # if the token is expired or some other issue try logging in using a browser
            print("Issue logging in with token trying manual...")
            driver = CustomChromeInstance.createInstance()
            self._client = tda.auth.client_from_login_flow(
                driver, TD_KEY, TD_URI, TD_TOKEN_PATH
            )

    def _get_stock_data(self, sym: str) -> StockData:
        return MarketData.get_stock_data(sym)

    def _get_option_data(self, option: OptionOrder) -> OptionData:
        return MarketData.get_option_data(option)

    def _get_latest_order(self) -> dict:
        return cast(
            dict,
            self._client.get_orders_by_path(
                TD_ACC_NUM,
                from_entered_datetime=datetime.now(),
                to_entered_datetime=datetime.now() + timedelta(1),
            ).json()[0],
        )

    def buy(self, order: StockOrder) -> None:
        ### PRE BUY INFO ###
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = self._get_current_time()

        ### BUY ###
        if order.order_type == OrderType.MARKET:
            self._market_buy(order)
        else:
            self._limit_buy(order)

        ### POST BUY INFO ###
        program_executed = self._get_current_time()
        post_stock_data = self._get_stock_data(order.sym)

        # broker executed time is left to save_report method since some brokers provide or don't provide it
        self._save_report(
            order.sym,
            ActionType.BUY,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
        )

    def sell(self, order: StockOrder) -> None:
        ### PRE BUY INFO ###
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = self._get_current_time()

        ### BUY ###
        if order.order_type == OrderType.MARKET:
            self._market_sell(order)
        else:
            self._limit_sell(order)

        ### POST BUY INFO ###
        program_executed = self._get_current_time()
        post_stock_data = self._get_stock_data(order.sym)

        # broker executed time is left to save_report method since some brokers provide or don't provide it
        self._save_report(
            order.sym,
            ActionType.SELL,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
        )

    def buy_option(self, order: OptionOrder) -> None:
        ### PRE BUY INFO ###
        pre_stock_data = self._get_option_data(order)
        program_submitted = self._get_current_time()

        ### BUY ###
        if order.option_type == OptionType.CALL:
            self._buy_call_option(order)
        else:
            self._buy_put_option(order)

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
        )
        time.sleep(1)

    def sell_option(self, order: OptionOrder) -> None:
        ### PRE SELL INFO ###
        pre_stock_data = self._get_option_data(order)
        program_submitted = self._get_current_time()

        ### SELL ###
        if order.option_type == OptionType.CALL:
            self._sell_call_option(order)
        else:
            self._sell_put_option(order)

        ### POST SELL INFO ###
        program_executed = self._get_current_time()
        post_stock_data = self._get_option_data(order)

        self._save_option_report(
            order,
            ActionType.SELL,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
        )
        time.sleep(1)

    def _market_buy(self, order: StockOrder) -> None:
        self._client.place_order(
            TD_ACC_NUM, equity_buy_market(order.sym, order.quantity).build()
        )

    def _market_sell(self, order: StockOrder) -> None:
        self._client.place_order(
            TD_ACC_NUM, equity_sell_market(order.sym, order.quantity).build()
        )

    def _limit_buy(self, order: StockOrder) -> Any:
        return NotImplementedError

    def _limit_sell(self, order: StockOrder) -> Any:
        return NotImplementedError

    def _buy_call_option(self, order: OptionOrder) -> None:
        sym = OptionSymbol(
            order.sym,
            datetime.strptime(order.expiration, "%Y-%m-%d"),
            "C",
            str(order.strike),
        ).build()

        self._client.place_order(TD_ACC_NUM, option_buy_to_open_market(sym, 1).build())

    def _sell_call_option(self, order: OptionOrder) -> None:
        sym = OptionSymbol(
            order.sym,
            datetime.strptime(order.expiration, "%Y-%m-%d"),
            "C",
            str(order.strike),
        ).build()

        self._client.place_order(
            TD_ACC_NUM, option_sell_to_close_market(sym, 1).build()
        )

    def _buy_put_option(self, order: OptionOrder) -> Any:
        return NotImplementedError

    def _sell_put_option(self, order: OptionOrder) -> Any:
        return NotImplementedError

    def _save_report(
        self,
        sym: str,
        action_type: ActionType,
        program_submitted: str,
        program_executed: str,
        pre_stock_data: StockData,
        post_stock_data: StockData,
        **kwargs: Union[str, float],
    ) -> None:
        order_data = self._get_latest_order()
        try:
            for activity in order_data["orderActivityCollection"]:
                TD_ct = activity["executionLegs"][0]["time"][11:]
                TD_ct_hour = str(int(TD_ct[:2]) - 7)
                if len(TD_ct_hour) == 1:
                    TD_ct_hour = "0" + TD_ct_hour
                broker_executed = TD_ct_hour + TD_ct[2:-5]

                self._add_report_to_file(
                    ReportEntry(
                        program_submitted,
                        program_executed,
                        broker_executed,
                        sym,
                        action_type,
                        activity["quantity"],
                        activity["executionLegs"][0]["price"],
                        activity["quantity"] * activity["executionLegs"][0]["price"],
                        pre_stock_data,
                        post_stock_data,
                        OrderType.MARKET,
                        len(order_data["orderActivityCollection"]) > 1,
                        order_data["orderId"],
                        activity["activityId"],
                        BrokerNames.TD,
                    )
                )

            self._save_report_to_file()
        except:
            logger.error("(TD) Error saving report")
            logger.error(order_data)

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
        order_data = self._get_latest_order()
        try:
            for activity in order_data["orderActivityCollection"]:
                TD_ct = activity["executionLegs"][0]["time"][11:]
                TD_ct_hour = str(int(TD_ct[:2]) - 7)
                if len(TD_ct_hour) == 1:
                    TD_ct_hour = "0" + TD_ct_hour
                broker_executed = TD_ct_hour + TD_ct[2:-5]

                self._add_option_report_to_file(
                    OptionReportEntry(
                        program_submitted,
                        program_executed,
                        broker_executed,
                        order.sym,
                        order.strike,
                        order.option_type,
                        order.expiration,
                        action_type,
                        activity["executionLegs"][0]["price"],
                        pre_stock_data,
                        post_stock_data,
                        OrderType.MARKET,
                        order_data["destinationLinkName"],
                        order_data["orderId"],
                        activity["activityId"],
                        BrokerNames.TD,
                    )
                )

            self._save_option_report_to_file()
        except:
            logger.error("(TD) Error saving option report")
            logger.error(order_data)

    def get_current_positions(self) -> tuple[list[StockOrder], list[OptionOrder]]:
        positions = self._client.get_account(
            TD_ACC_NUM, fields=[tda.client.Client.Account.Fields.POSITIONS]
        ).json()["securitiesAccount"]["positions"]
        current_positions: list[StockOrder] = []
        current_option_positions: list[OptionOrder] = []
        for position in positions:
            if position["instrument"]["assetType"] == "OPTION":
                symbol, month, date, year, strike, option_type = position["instrument"][
                    "description"
                ].split(" ")
                option_type = (
                    OptionType.CALL if option_type.upper() == "CALL" else OptionType.PUT
                )
                current_option_positions.append(
                    OptionOrder(
                        symbol,
                        option_type,
                        strike,
                        f"{year}-{datetime.strptime(month,'%b').strftime('%m')}-{date}",
                    )
                )
            else:
                current_positions.append(
                    StockOrder(
                        sym=position["instrument"]["symbol"],
                        quantity=position["longQuantity"],
                    )
                )

        return current_positions, current_option_positions

    # def temp(self, id):
    #     res = self._client.get_order(id, TD_ACC_NUM).json()
    #     print(res)


if __name__ == "__main__":
    td = TDAmeritrade(Path("temp.csv"), BrokerNames.TD, Path("temp_option.csv"))
    td.login()
    pass
