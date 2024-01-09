from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

import pandas as pd

from utils.report.report import OrderType, StockData, ReportEntry, ActionType, BrokerNames

NULL_ENTRY = pd.Series(index = ['Date', 'Program Submitted', 'Program Executed', 'Broker Executed', 'Symbol', 'Broker', 'Action', 'Size', 'Price', 'Dollar Amt', 'Pre Quote', 'Post Quote', 'Pre Bid', 'Pre Ask', 'Post Bid', 'Post Ask', 'Pre Volume', 'Post Volume', 'Order Type', 'Split', 'Order ID', 'Activity ID'])
class Broker(ABC):
    THRESHOLD = 1000

    def __init__(self, report_file: Union[Path, str], broker_name: BrokerNames):
        self._broker_name = broker_name
        self._executed_trades = []
        if not isinstance(report_file, Path):
            report_file = Path(report_file)
        self._report_file = report_file
        self._error_count = 0

    @abstractmethod
    def login(self):
        pass

    @abstractmethod
    def _get_stock_data(self, sym: str):
        pass

    @abstractmethod
    def buy(self, sym: str, amount: int):
        pass

    @abstractmethod
    def sell(self, sym: str, amount: int):
        pass

    @abstractmethod
    def _market_buy(self, sym: str, amount: int):
        pass

    @abstractmethod
    def _market_sell(self, sym: str, amount: int):
        pass

    @abstractmethod
    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        pass

    @abstractmethod
    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        pass

    @abstractmethod
    def get_current_positions(self):
        pass
    @abstractmethod
    def resolve_errors(self):
        pass

    def _add_report(self, program_submitted: str, program_executed: str,
                    broker_executed: str, sym: str, action: ActionType, number_of_shares: int,
                    price: Union[float, str], dollar_amt: Union[float, str], pre_stock_data: StockData,
                    post_stock_data: StockData, order_type: OrderType, split: bool,
                    order_id: str, activity_id: str):
        self._executed_trades.append(
            ReportEntry(program_submitted, program_executed, broker_executed, sym,
                        action, number_of_shares, price,
                        dollar_amt, pre_stock_data, post_stock_data, order_type, split,
                        order_id, activity_id, self._broker_name))

    def save_report(self):
        with self._report_file.open("a") as file:
            for report in self._executed_trades:
                file.write(str(report))

        self._executed_trades.clear()

    def name(self):
        return self._broker_name.value if self._broker_name else self.__class__.__name__
