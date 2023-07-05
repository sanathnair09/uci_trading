from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from utils.report import OrderType, StockData, ReportEntry, ActionType, BrokerNames


class Broker(ABC):
    def __init__(self, report_file: Union[Path, str]):
        self._executed_trades = []
        if type(report_file) is not Path:
            report_file = Path(report_file)
        self._report_file = report_file
        if not self._report_file.exists():
            self._report_file.touch() # TODO: if changing the columns of report file also modify here
            self._report_file.write_text("Date,Program Submitted,Program Executed,Broker Executed,Symbol,Broker,Action,Size,Price,Dollar Amt,Pre Quote,Post Quote,Pre Bid,Pre Ask,Post Bid,Post Ask,Pre Volume,Post Volume,Order Type,Split,Order ID,Activity ID\n")

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

    def __handle_none_value(self, value):
        return " " if value is None else value
    def _add_report(self, program_submitted: str, program_executed: str,
                    broker_executed: str, sym: str, action: ActionType, number_of_shares: int,
                    price: float, dollar_amt: float, pre_stock_data: StockData,
                    post_stock_data: StockData, order_type: OrderType, split: bool,
                    order_id: str, activity_id: str, broker: BrokerNames):
        # TODO: make None into "" or " "
        # args = locals()
        # for key, value in args.items():
        #     print(key, value)
        #     args[key] = self.__handle_none_value(value)
        # print(locals())
        self._executed_trades.append(
            ReportEntry(program_submitted, program_executed, broker_executed, sym,
                        action, number_of_shares, price,
                        dollar_amt, pre_stock_data, post_stock_data, order_type, split,
                        order_id, activity_id, broker))

    def save_report(self):
        with self._report_file.open("a") as file:
            for report in self._executed_trades:
                file.write(str(report))

        self._executed_trades.clear()

    def name(self):
        return self.__class__.__name__
