from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Union


class ActionType(Enum):
    BUY = "Buy"
    SELL = "Sell"
    OPEN = "open"
    CLOSE = "close"


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


class OrderType(Enum):
    MARKET = "Market"
    LIMIT = "Limit"


class BrokerNames(Enum):
    TD = "TD" # TD Ameritrade
    RH = "RH" # Robinhood
    ET = "ET" # ETrade
    E2 = "E2" # ETrade
    SB = "SB" # Schwab
    FD = "FD" # Fidelity
    IF = "IF"  # IBKR free
    VD = "VD" # Vanguard


@dataclass
class StockData:
    ask: float
    bid: float
    quote: float
    volume: float

    def __str__(self):
        return f"{self.ask},{self.bid},{self.quote},{self.volume}"


@dataclass
class OptionData(StockData):
    volatility: float
    delta: float
    theta: float
    gamma: float
    vega: float
    rho: float
    underlying_price: float
    in_the_money: bool

    def __str__(self):
        return f"{self.ask},{self.bid},{self.quote},{self.volume},{self.volatility},{self.delta},{self.theta},{self.gamma},{self.vega},{self.rho},{self.underlying_price},{self.in_the_money}"


NULL_STOCK_DATA = StockData("", "", "", "")  # type: ignore
NULL_OPTION_DATA = OptionData("", "", "", "", "", "", "", "", "", "", "", "")  # type: ignore


@dataclass
class ReportEntry:
    program_submitted: str  # time before placing order
    program_executed: str  # time after placing order
    broker_executed: str  # time executed according to broker info
    sym: str  # symbol
    action: ActionType  # Buy or Sell
    quantity: int
    price: Union[float, str]  # price of a share when bought/sold
    dollar_amt: Union[float, str]  # price * number_of_shares
    pre_stock_data: StockData  # ask, bid, quote, vol before placing order
    post_stock_data: StockData  # ask, bid, quote, vol after placing order
    # top_mover: any
    order_type: OrderType  # market, limit
    split: bool  # was the order split into multiple
    order_id: str
    activity_id: str
    broker: BrokerNames

    def __str__(self):
        return f"{datetime.now().strftime('%x')},{self.program_submitted},{self.program_executed},{self.broker_executed},{self.sym},{self.broker.value},{self.action.value},{self.quantity},{self.price},{(self.dollar_amt)},{format_quote_data(self.pre_stock_data, self.post_stock_data)},{self.order_type.value},{self.split},{self.order_id},{self.activity_id}\n"


@dataclass
class OptionReportEntry:
    program_submitted: str  # time before placing order
    program_executed: str  # time after placing order
    broker_executed: str  # time executed according to broker info
    sym: str  # symbol
    strike: float
    option_type: OptionType  # Call or Put
    expiration: str
    action: ActionType  # Buy or Sell
    price: float  # price of a share when bought/sold
    pre_stock_data: OptionData  # ask, bid, quote, vol, greeks before placing order
    post_stock_data: OptionData  # ask, bid, quote, vol after, greeks placing order
    order_type: OrderType  # market, limit
    venue: str
    order_id: str
    activity_id: str
    broker: BrokerNames

    def __str__(self):
        return f"{datetime.now().strftime('%x')},{self.program_submitted},{self.program_executed},{self.broker_executed},{self.sym},{self.broker.value},{self.action.value},{self.price},{format_option_data(self.pre_stock_data, self.post_stock_data)},{self.order_type.value},{self.venue},{self.order_id},{self.activity_id}\n"


def format_quote_data(pre: StockData, post: StockData):
    return f"{pre.quote},{post.quote},{pre.bid},{pre.ask},{post.bid},{post.ask},{pre.volume},{post.volume}"


def format_option_data(pre: OptionData, post: OptionData):
    return f"{pre.quote},{post.quote},{pre.bid},{pre.ask},{post.bid},{post.ask},{pre.volume},{post.volume},{pre.volatility},{post.volatility},{pre.delta},{post.delta},{pre.theta},{post.theta},{pre.gamma},{post.gamma},{pre.vega},{post.vega},{pre.rho},{post.rho},{pre.underlying_price},{post.underlying_price},{pre.in_the_money},{post.in_the_money}"


if __name__ == "__main__":
    pass
