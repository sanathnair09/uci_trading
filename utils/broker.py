from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from utils.report.report import (
    OptionData,
    OptionReportEntry,
    OptionType,
    OrderType,
    StockData,
    ReportEntry,
    ActionType,
    BrokerNames,
)


NULL_ENTRY = pd.Series(
    index=[
        "Date",
        "Program Submitted",
        "Program Executed",
        "Broker Executed",
        "Symbol",
        "Broker",
        "Action",
        "Size",
        "Price",  # price we got
        "Dollar Amt",
        "Pre Quote",
        "Post Quote",
        "Pre Bid",
        "Pre Ask",
        "Post Bid",
        "Post Ask",
        "Pre Volume",
        "Post Volume",
        "Order Type",
        "Split",
        "Order ID",
        "Activity ID",
    ]
)


@dataclass
class StockOrder:
    sym: str
    quantity: float
    price: float = 0.0
    order_type: OrderType = OrderType.MARKET

    def __str__(self) -> str:
        return f"{self.sym},{self.quantity},{self.price},{self.order_type}"


@dataclass
class OptionOrder:
    sym: str
    option_type: OptionType
    strike: str
    expiration: str
    order_type: OrderType = OrderType.MARKET

    def formatted_expiration(self) -> str:
        return datetime.strptime(self.expiration, "%Y-%m-%d").strftime("%m/%d/%Y")

    def __str__(self) -> str:
        """
        needed to allow conversion: OptionOrder <-> file
        """
        return f"{self.sym}-{self.option_type.value}-{self.strike}-{self.formatted_expiration()}"


class Broker(ABC):
    THRESHOLD = 1200

    def __init__(
        self,
        report_file: Path,
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        self._broker_name = broker_name
        self._executed_trades: list[ReportEntry] = []
        self._executed_option_trades: list[OptionReportEntry] = []

        self._report_file = report_file

        if option_report_file and not isinstance(option_report_file, Path):
            option_report_file = Path(option_report_file)
        self._option_report_file = option_report_file

        self._error_count = 0

    def _get_current_time(self) -> str:
        return datetime.now().strftime("%X:%f")

    def _add_report_to_file(self, report_entry: ReportEntry) -> None:
        self._executed_trades.append(report_entry)

    def _add_option_report_to_file(
        self, option_report_entry: OptionReportEntry
    ) -> None:
        self._executed_option_trades.append(option_report_entry)

    def _save_report_to_file(self) -> None:
        with self._report_file.open("a") as file:
            for report in self._executed_trades:
                file.write(str(report))

        self._executed_trades.clear()

    def _save_option_report_to_file(self) -> None:
        if self._option_report_file:
            with self._option_report_file.open("a") as file:
                for report in self._executed_option_trades:
                    file.write(str(report))

        self._executed_option_trades.clear()

    def name(self) -> str:
        return self._broker_name.value if self._broker_name else self.__class__.__name__

    @abstractmethod
    def buy(self, order: StockOrder) -> None:
        pass

    @abstractmethod
    def sell(self, order: StockOrder) -> None:
        pass

    @abstractmethod
    def buy_option(self, order: OptionOrder) -> None:
        pass

    @abstractmethod
    def sell_option(self, order: OptionOrder) -> None:
        pass

    @abstractmethod
    def login(self) -> None:
        pass

    @abstractmethod
    def _get_stock_data(self, sym: str) -> StockData:
        pass

    @abstractmethod
    def _get_option_data(self, order: OptionOrder) -> OptionData:
        pass

    @abstractmethod
    def _market_buy(self, order: StockOrder) -> Union[str, dict, None]:
        pass

    @abstractmethod
    def _market_sell(self, order: StockOrder) -> Union[str, dict, None]:
        pass

    @abstractmethod
    def _limit_buy(self, order: StockOrder) -> Union[str, dict, None]:
        pass

    @abstractmethod
    def _limit_sell(self, order: StockOrder) -> Union[str, dict, None]:
        pass

    @abstractmethod
    def _buy_call_option(self, order: OptionOrder) -> Union[str, dict, None]:
        pass

    @abstractmethod
    def _sell_call_option(self, order: OptionOrder) -> Union[str, dict, None]:
        pass

    @abstractmethod
    def _buy_put_option(self, order: OptionOrder) -> Union[str, dict, None]:
        pass

    @abstractmethod
    def _sell_put_option(self, order: OptionOrder) -> Union[str, dict, None]:
        pass

    @abstractmethod
    def get_current_positions(self) -> tuple[list[StockOrder], list[OptionOrder]]:
        pass

    @abstractmethod
    def _save_report(
        self,
        sym: str,
        action_type: ActionType,
        program_submitted: str,
        program_executed: str,
        pre_stock_data: StockData,
        post_stock_data: StockData,
        **kwargs: Union[str, float],
    ):
        pass

    @abstractmethod
    def _save_option_report(
        self,
        order: OptionOrder,
        action_type: ActionType,
        program_submitted: str,
        program_executed: str,
        pre_stock_data: OptionData,
        post_stock_data: OptionData,
        **kwargs: str,
    ):
        pass
