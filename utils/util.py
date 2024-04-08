from datetime import datetime
from typing import Any
from utils.broker import OptionOrder, StockOrder

from utils.report.report import OptionType, OrderType


def repeat_on_fail(times: int = 5, default_return=False) -> Any:
    def _repeat(func):
        def wrapper(*args, **kwargs):
            _times = times
            while _times != 0:
                try:
                    res = func(*args, **kwargs)
                    return res
                except Exception as e:
                    if e:
                        print(e)
                    _times -= 1
            return default_return

        return wrapper

    return _repeat


def repeat(times: int = 5) -> Any:
    def _repeat(func):
        def wrapper(*args, **kwargs):
            _times = times
            while _times != 0:
                func(*args, **kwargs)
                _times -= 1

        return wrapper

    return _repeat


def calculate_num_stocks_to_buy(dollar_amt: float, stock_price: float):
    return max(1, round(dollar_amt / stock_price))


def convert_to_float(string, default: Any = ""):
    return float(string) if string != "" else default


def process_option_input() -> list[OptionOrder]:
    """
    input format should follow: SYM-Call/Put-STRIKE-MM/DD/YYYY,(next option),...
    """
    temp = input("Enter option list to trade for today: ")
    parts = temp.split(",")
    orders: list[OptionOrder] = []
    if parts[0] != "":
        for part in parts:
            orders.append(parse_option_string(part))  # type: ignore

    return orders


def parse_option_string(option_string: str):
    """
    SYM-Call/Put-STRIKE-MM/DD/YYYY
    """
    if option_string == "":
        return None
    sym, option_type, strike, expiration = option_string.split("-")
    option_type = OptionType.CALL if option_type.upper() == "CALL" else OptionType.PUT
    expiration = datetime.strptime(expiration, "%m/%d/%Y").strftime("%Y-%m-%d")
    return OptionOrder(sym, OrderType.MARKET, option_type, strike, expiration)


def format_list_of_orders(orders: list[StockOrder]):
    return "-".join([str(order) for order in orders])


def parse_stock_string(stock_string: str):
    parts = stock_string.split("-")
    if parts[0] == "":
        return []
    res: list[StockOrder] = []
    for part in parts:
        sym, quantity, price, order_type = part.split(",")
        order_type = (
            OrderType.MARKET if order_type == "OrderType.MARKET" else OrderType.LIMIT
        )
        res.append(StockOrder(sym, float(quantity), float(price), order_type))
    return res


if __name__ == "__main__":
    print(parse_option_string("MRNA-Call-110.00-03/15/2024"))
