import json
from datetime import datetime


def repeat_on_fail(times: int = 5, default_return = False) -> any:
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


def repeat(times: int = 5) -> any:
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

def convert_to_float(string, default=''):
    return float(string) if string != '' else default