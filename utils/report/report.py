from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, TypeVar, Union

T = TypeVar("T")


def check_none(value: T) -> Union[T, str]:
    return value if value is not None else ""


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
    TD = "TD"  # TD Ameritrade
    RH = "RH"  # Robinhood
    ET = "ET"  # ETrade
    E2 = "E2"  # ETrade
    SB = "SB"  # Schwab
    FD = "FD"  # Fidelity
    IF = "IF"  # IBKR free
    VD = "VD"  # Vanguard


@dataclass
class StockData:
    ask: float
    bid: float
    quote: float
    volume: float

    def __str__(self) -> str:
        return f"{self.ask},{self.bid},{self.quote},{self.volume}"


@dataclass
class OptionData(StockData):
    volatility: float
    delta: float
    theta: float
    gamma: float
    vega: float
    rho: float
    underlying_price: Optional[float]
    in_the_money: Optional[bool]

    def __str__(self) -> str:
        return f"{self.ask},{self.bid},{self.quote},{self.volume},{self.volatility},{self.delta},{self.theta},{self.gamma},{self.vega},{self.rho},{check_none(self.underlying_price)},{self.in_the_money}"


NULL_STOCK_DATA = StockData("", "", "", "")  # type: ignore
NULL_OPTION_DATA = OptionData("", "", "", "", "", "", "", "", "", "", "", "")  # type: ignore

# add field for new column and in str function
@dataclass
class ReportEntry:
    program_submitted: str  # time before placing order
    program_executed: str  # time after placing order
    broker_executed: Optional[str]  # time executed according to broker info
    sym: str  # symbol
    action: ActionType  # Buy or Sell
    quantity: float
    price: Optional[float]  # price of a share when bought/sold
    dollar_amt: Optional[float]  # price * number_of_shares
    pre_stock_data: StockData  # ask, bid, quote, vol before placing order
    post_stock_data: StockData  # ask, bid, quote, vol after placing order
    order_type: OrderType  # market, limit
    split: bool  # was the order split into multiple
    order_id: Optional[str]
    activity_id: Optional[str]
    broker: BrokerNames
    destination: str = ""

    def __str__(self) -> str:
        return f"{datetime.now().strftime('%x')},{self.program_submitted},{self.program_executed},{self.broker_executed},{self.sym},{self.broker.value},{self.action.value},{self.quantity},{self.price},{(self.dollar_amt)},{format_quote_data(self.pre_stock_data, self.post_stock_data)},{self.order_type.value},{self.split},{self.order_id},{self.activity_id},{self.destination}\n"

# add field for new column and in str function
@dataclass
class OptionReportEntry:
    program_submitted: str  # time before placing order
    program_executed: str  # time after placing order
    broker_executed: Optional[str]  # time executed according to broker info
    sym: str  # symbol
    strike: str
    option_type: OptionType  # Call or Put
    expiration: str
    action: ActionType  # Buy or Sell
    quantify: int
    price: Optional[float]  # price of a share when bought/sold
    pre_stock_data: OptionData  # ask, bid, quote, vol, greeks before placing order
    post_stock_data: OptionData  # ask, bid, quote, vol after, greeks placing order
    order_type: OrderType  # market, limit
    venue: Optional[str]
    order_id: Optional[str]
    activity_id: Optional[str]
    broker: BrokerNames

    def __str__(self) -> str:
        return f"{datetime.now().strftime('%x')},{self.program_submitted},{self.program_executed},{self.broker_executed},{self.sym},{self.strike},{self.option_type.value[0].upper()},{self.expiration},{self.quantify},{self.broker.value},{self.action.value},{self.price},{format_option_data(self.pre_stock_data, self.post_stock_data)},{self.order_type.value},{self.venue},{self.order_id},{self.activity_id}\n"

@dataclass
class TwentyFourReportEntry:
    date: str
    program_submitted: str
    broker_executed: Optional[str]  # time executed according to broker info
    sym: str  # symbol
    broker: str
    action: str  # Buy or Sell
    quantity: int
    price: Optional[float]  # price of a share when bought/sold
    spread: float
    ask: float
    bid: float
    limit_price: float

    def __str__(self) -> str:
        return f"{self.date},{self.program_submitted},{self.broker_executed},{self.sym},{self.action},{self.quantity},{self.broker},{self.price},{self.spread},{self.ask},{self.bid},{self.limit_price} \n"

def format_quote_data(pre: StockData, post: StockData) -> str:
    return f"{pre.quote},{post.quote},{pre.bid},{pre.ask},{post.bid},{post.ask},{pre.volume},{post.volume}"


def format_option_data(pre: OptionData, post: OptionData) -> str:
    return f"{pre.quote},{post.quote},{pre.bid},{pre.ask},{post.bid},{post.ask},{pre.volume},{post.volume},{pre.volatility},{post.volatility},{pre.delta},{post.delta},{pre.theta},{post.theta},{pre.gamma},{post.gamma},{pre.vega},{post.vega},{pre.rho},{post.rho},{pre.underlying_price},{post.underlying_price},{pre.in_the_money},{post.in_the_money}"


if __name__ == "__main__":
    pass
