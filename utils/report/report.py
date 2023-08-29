from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ActionType(Enum):
    BUY = "Buy"
    SELL = "Sell"


class OrderType(Enum):
    MARKET = "Market"
    LIMIT = "Limit"


class BrokerNames(Enum):
    TD = "TD"
    RH = "RH"
    ET = "ET"
    E2 = "E2"
    SB = "SB"
    FD = "FD"
    IF = "IF"  # IBKR free


@dataclass
class StockData:
    ask: float
    bid: float
    quote: float
    volume: float

    def __str__(self):
        return f"{self.ask},{self.bid},{self.quote},{self.volume}"


def format_quote_data(pre: StockData, post: StockData):
    return f"{pre.quote},{post.quote},{pre.bid},{pre.ask},{post.bid},{post.ask},{pre.volume},{post.volume}"


@dataclass
class ReportEntry:
    program_submitted: str  # time before placing order
    program_executed: str  # time after placing order
    broker_executed: str  # time executed according to broker info
    sym: str  # symbol
    action: ActionType  # Buy or Sell
    number_of_shares: int
    price: float  # price of a share when bought/sold
    dollar_amt: float  # price * number_of_shares
    pre_stock_data: StockData  # ask, bid, quote, vol before placing order
    post_stock_data: StockData  # ask, bid, quote, vol after placing order
    # top_mover: any
    order_type: OrderType  # market, limit
    split: bool  # was the order split into multiple
    order_id: str
    activity_id: str
    broker: BrokerNames

    def __str__(self):
        return f"{datetime.now().strftime('%x')},{self.program_submitted},{self.program_executed},{self.broker_executed},{self.sym},{self.broker.value},{self.action.value},{self.number_of_shares},{self.price},{self.dollar_amt},{format_quote_data(self.pre_stock_data, self.post_stock_data)},{self.order_type.value},{self.split},{self.order_id},{self.activity_id}\n"


if __name__ == '__main__':
    pass
    # a = ReportEntry(None, None, None, None, None, None, None, None, None, None, None, None, None,
    #                 None, None, None)
    # print(a)
