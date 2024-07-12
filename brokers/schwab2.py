from datetime import datetime, timedelta
import json
from pathlib import Path
import time
from typing import Any, Optional, cast
from loguru import logger
from schwab import auth, client
from schwab.orders.equities import equity_buy_market, equity_sell_market
from schwab.orders.options import (  # type: ignore[import-untyped]
    option_buy_to_open_market,
    option_sell_to_close_market,
    OptionSymbol,
)
from brokers import SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_TOKEN_PATH, SCHWAB_URI
from utils.broker import Broker, OptionOrder, StockOrder
from utils.report.report import (
    NULL_OPTION_DATA,
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


class Schwab(Broker):
    def __init__(
        self,
        report_file: Path,
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        super().__init__(report_file, broker_name, option_report_file)

    def _get_stock_data(self, sym: str) -> StockData:
        res = self._client.get_quote(sym).json()[sym]["quote"]
        return StockData(
            res["askPrice"], res["bidPrice"], res["lastPrice"], res["totalVolume"]
        )

    def _get_option_data(self, order: OptionOrder) -> OptionData:
        contract_type = (
            client.Client.Options.ContractType.CALL
            if order.option_type == OptionType.CALL
            else client.Client.Options.ContractType.PUT
        )
        date = datetime.strptime(order.expiration, "%Y-%m-%d")
        option_data = self._client.get_option_chain(
            order.sym,
            contract_type=contract_type,
            strike=order.strike,
            from_date=date,
            to_date=date,
        ).json()
        if order.option_type == OptionType.CALL:
            possibilities = option_data["callExpDateMap"]
        else:
            possibilities = option_data["putExpDateMap"]
        for keys in possibilities:
            for key in possibilities[keys]:
                if float(key) == float(order.strike):
                    return OptionData(
                        possibilities[keys][key][0]["ask"],
                        possibilities[keys][key][0]["bid"],
                        possibilities[keys][key][0]["last"],
                        possibilities[keys][key][0]["totalVolume"],
                        possibilities[keys][key][0]["volatility"],
                        possibilities[keys][key][0]["delta"],
                        possibilities[keys][key][0]["theta"],
                        possibilities[keys][key][0]["gamma"],
                        possibilities[keys][key][0]["vega"],
                        possibilities[keys][key][0]["rho"],
                        round(option_data["underlyingPrice"], 4),
                        possibilities[keys][key][0]["inTheMoney"],
                    )
        return NULL_OPTION_DATA

    def _get_latest_order(self) -> dict:
        return cast(
            dict,
            self._client.get_orders_for_account(
                self._hash,
                from_entered_datetime=datetime.now(),
                to_entered_datetime=datetime.now() + timedelta(1),
            ).json()[0],
        )

    def login(self) -> None:
        try:
            self._client = auth.client_from_token_file(
                SCHWAB_TOKEN_PATH, SCHWAB_APP_KEY, SCHWAB_APP_SECRET
            )
        except:
            self._client = auth.client_from_manual_flow(
                SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_URI, SCHWAB_TOKEN_PATH
            )
        self._hash = self._client.get_account_numbers().json()[0]["hashValue"]

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
            self._hash, equity_buy_market(order.sym, order.quantity)
        )

    def _market_sell(self, order: StockOrder) -> None:
        self._client.place_order(
            self._hash, equity_sell_market(order.sym, order.quantity)
        )

    def _limit_buy(self, order: StockOrder) -> None:
        raise NotImplementedError

    def _limit_sell(self, order: StockOrder) -> None:
        raise NotImplementedError

    def _buy_call_option(self, order: OptionOrder) -> None:
        sym = OptionSymbol(
            order.sym,
            datetime.strptime(order.expiration, "%Y-%m-%d"),
            "C",
            str(order.strike),
        ).build()
        self._client.place_order(
            self._hash, option_buy_to_open_market(sym, order.quantity)
        )

    def _sell_call_option(self, order: OptionOrder) -> None:
        sym = OptionSymbol(
            order.sym,
            datetime.strptime(order.expiration, "%Y-%m-%d"),
            "C",
            str(order.strike),
        ).build()

        self._client.place_order(
            self._hash, option_sell_to_close_market(sym, 1).build()
        )

    def _buy_put_option(self, order: OptionOrder) -> None:
        raise NotImplementedError

    def _sell_put_option(self, order: OptionOrder) -> None:
        raise NotImplementedError

    def get_current_positions(self) -> tuple[list[StockOrder], list[OptionOrder]]:
        positions = self._client.get_account(
            self._hash, fields=[client.Client.Account.Fields.POSITIONS]
        ).json()
        positions = positions["securitiesAccount"]["positions"]
        current_positions: list[StockOrder] = []
        current_option_positions: list[OptionOrder] = []
        for position in positions:
            if position["instrument"]["assetType"] == "OPTION":
                symbol, desc = position["instrument"]["symbol"].split()
                expiration = desc[:6]
                option_type = (
                    OptionType.CALL if desc[6] == "C" else OptionType.PUT
                )
                strike = float(desc[7:]) / 1000

                current_option_positions.append(
                    OptionOrder(
                        symbol,
                        option_type,
                        str(strike),
                        f"20{expiration[:2]}-{expiration[2:4]}-{expiration[4:]}",
                        quantity=position["longQuantity"],
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

    def _save_report(
        self,
        sym: str,
        action_type: ActionType,
        program_submitted: str,
        program_executed: str,
        pre_stock_data: StockData,
        post_stock_data: StockData,
        **kwargs: Any,
    ) -> None:
        order_data = self._get_latest_order()
        try:
            for activity in order_data["orderActivityCollection"]:
                SB_ct = activity["executionLegs"][0]["time"][11:]
                SB_ct_hour = str(int(SB_ct[:2]) - 7)
                if len(SB_ct_hour) == 1:
                    SB_ct_hour = "0" + SB_ct_hour
                broker_executed = SB_ct_hour + SB_ct[2:-5]

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
                        BrokerNames.SB,
                        order_data["destinationLinkName"],
                    )
                )

            self._save_report_to_file()
        except:
            logger.error("(SB Error saving report")
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
                SB_ct = activity["executionLegs"][0]["time"][11:]
                SB_ct_hour = str(int(SB_ct[:2]) - 7)
                if len(SB_ct_hour) == 1:
                    SB_ct_hour = "0" + SB_ct_hour
                broker_executed = SB_ct_hour + SB_ct[2:-5]

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
                        order.quantity,
                        activity["executionLegs"][0]["price"],
                        pre_stock_data,
                        post_stock_data,
                        OrderType.MARKET,
                        order_data["destinationLinkName"],
                        order_data["orderId"],
                        activity["activityId"],
                        BrokerNames.SB,
                    )
                )

            self._save_option_report_to_file()
        except:
            logger.error("SB Error saving option report")
            logger.error(order_data)


if __name__ == "__main__":
    s = Schwab(Path("temp.csv"), BrokerNames.SB, Path("temp_option.csv"))
    s.login()
    print(s.get_current_positions())