from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

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
    price: float
    order_type: OrderType

    def __str__(self) -> str:
        return f"{self.sym},{self.quantity},{self.price},{self.order_type}"


@dataclass
class OptionOrder:
    sym: str
    order_type: OrderType
    option_type: OptionType
    strike: str
    expiration: str

    def formatted_expiration(self) -> str:
        return datetime.strptime(self.expiration, '%Y-%m-%d').strftime('%m/%d/%Y')

    def __str__(self) -> str:
        """
        needed to allow conversion: OptionOrder <-> file
        """
        return f"{self.sym}-{self.option_type.value}-{self.strike}-{self.formatted_expiration()}"


class Broker(ABC):
    THRESHOLD = 1200

    def __init__(
        self,
        report_file: Union[Path, str],
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        self._broker_name = broker_name
        self._executed_trades = []
        self._executed_option_trades = []

        if not isinstance(report_file, Path):
            report_file = Path(report_file)
        self._report_file = report_file

        if option_report_file and not isinstance(option_report_file, Path):
            option_report_file = Path(option_report_file)
        self._option_report_file = option_report_file

        self._error_count = 0

    def _get_current_time(self):
        return datetime.now().strftime("%X:%f")

    def _add_report_to_file(self, report_entry: ReportEntry):
        self._executed_trades.append(report_entry)

    def _add_option_report_to_file(self, option_report_entry: OptionReportEntry):
        self._executed_option_trades.append(option_report_entry)

    def _save_report_to_file(self):
        with self._report_file.open("a") as file:
            for report in self._executed_trades:
                file.write(str(report))

        self._executed_trades.clear()

    def _save_option_report_to_file(self):
        if self._option_report_file:
            with self._option_report_file.open("a") as file:
                for report in self._executed_option_trades:
                    file.write(str(report))

        self._executed_option_trades.clear()

    def name(self):
        return self._broker_name.value if self._broker_name else self.__class__.__name__

    @abstractmethod
    def buy(self, order: StockOrder):
        pass

    @abstractmethod
    def sell(self, order: StockOrder):
        pass

    @abstractmethod
    def buy_option(self, order: OptionOrder):
        pass

    @abstractmethod
    def sell_option(self, order: OptionOrder):
        pass

    @abstractmethod
    def login(self):
        pass

    @abstractmethod
    def _get_stock_data(self, sym: str) -> StockData:
        pass

    @abstractmethod
    def _get_option_data(self, order: OptionOrder) -> OptionData:
        pass

    @abstractmethod
    def _market_buy(self, order: StockOrder):
        pass

    @abstractmethod
    def _market_sell(self, order: StockOrder):
        pass

    @abstractmethod
    def _limit_buy(self, order: StockOrder):
        pass

    @abstractmethod
    def _limit_sell(self, order: StockOrder):
        pass

    @abstractmethod
    def _buy_call_option(self, order: OptionOrder):
        pass

    @abstractmethod
    def _sell_call_option(self, order: OptionOrder):
        pass

    @abstractmethod
    def _buy_put_option(self, order: OptionOrder):
        pass

    @abstractmethod
    def _sell_put_option(self, order: OptionOrder):
        pass

    @abstractmethod
    def get_current_positions(self) -> list[StockOrder]:
        pass

    @abstractmethod
    def _save_report(
        self,
        sym: str,
        action_type: ActionType,
        program_submitted,
        program_executed,
        pre_stock_data: StockData,
        post_stock_data: StockData,
        **kwargs,
    ):
        pass

    @abstractmethod
    def _save_option_report(
        self,
        order: OptionOrder,
        action_type: ActionType,
        program_submitted,
        program_executed,
        pre_stock_data: OptionData,
        post_stock_data: OptionData,
        **kwargs,
    ):
        pass
