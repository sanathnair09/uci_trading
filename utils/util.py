from datetime import datetime
from typing import Any, Callable, Optional, no_type_check
from utils.broker import OptionOrder, StockOrder

from utils.report.report import OptionType, OrderType

@no_type_check
def repeat_on_fail(times: int = 5, default_return=False):
    def _repeat(func) :
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

@no_type_check
def repeat(times: int = 5):
    def _repeat(func):
        def wrapper(*args, **kwargs):
            _times = times
            while _times != 0:
                func(*args, **kwargs)
                _times -= 1

        return wrapper

    return _repeat


def calculate_num_stocks_to_buy(dollar_amt: float, stock_price: float) -> int:
    return max(1, round(dollar_amt / stock_price))


def convert_to_float(string: str) -> Optional[float]:
    return float(string) if string != "" else None


def process_option_input() -> list[OptionOrder]:
    """
    input format should follow: SYM-Call/Put-STRIKE-MM/DD/YYYY,(next option),...
    """
    temp = input("Enter option list to trade for today: ")
    parts = temp.split(",")
    orders: list[OptionOrder] = []
    if parts[0] != "":
        for part in parts:
            option = parse_option_string(part)
            if option:
                orders.append(option)

    return orders


def parse_option_string(option_string: str) -> Optional[OptionOrder]:
    """
    SYM-Call/Put-STRIKE-MM/DD/YYYY
    """
    if option_string == "":
        return None
    sym, option_type_str, strike, expiration_str = option_string.split("-")
    option_type = OptionType.CALL if option_type_str.upper() == "CALL" else OptionType.PUT
    expiration = datetime.strptime(expiration_str, "%m/%d/%Y").strftime("%Y-%m-%d")
    return OptionOrder(sym, option_type, strike, expiration, OrderType.MARKET)


def format_list_of_orders(orders: list[StockOrder]) -> str:
    return "-".join([str(order) for order in orders])


def parse_stock_string(stock_string: str) -> list[StockOrder]:
    parts = stock_string.split("-")
    if parts[0] == "":
        return []
    res: list[StockOrder] = []
    for part in parts:
        sym, quantity, price, order_type_str = part.split(",")
        order_type = (
            OrderType.MARKET if order_type_str == "OrderType.MARKET" else OrderType.LIMIT
        )
        res.append(StockOrder(sym, float(quantity), float(price), order_type))
    return res


if __name__ == "__main__":
    pass