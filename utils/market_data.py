from pathlib import Path
from typing import Any, cast

import robin_stocks.robinhood as rh  # type: ignore [import-untyped]
from brokers.robinhood import Robinhood
from utils.broker import OptionOrder
from utils.report.report import (
    NULL_OPTION_DATA,
    BrokerNames,
    OptionData,
    OptionType,
    StockData,
)
from utils.util import calculate_num_stocks_to_buy, parse_option_string

SIGNED_IN = False


class MarketData:
    """
    Uses TD Ameritrade API to get stock and option data
    """

    @staticmethod
    def sign_in() -> None:
        """ """
        global SIGNED_IN
        if SIGNED_IN:
            return
        Robinhood.login_custom("RH")
        SIGNED_IN = True

    @staticmethod
    def validate_stock(sym: str) -> bool:
        """
        checks if symbol is valid
        """
        MarketData.sign_in()
        return rh.get_quotes(sym)[0] is not None

    @staticmethod
    def get_stock_amount(sym: str) -> tuple[int, float]:
        """
        calculates the quantity of stocks needed to buy 100 shares at the current price
        :returns (quantity, price)
        """
        MarketData.sign_in()
        price = float(rh.get_quotes(sym)[0]["last_trade_price"])
        return calculate_num_stocks_to_buy(100, price), price

    @staticmethod
    def get_stock_data(sym: str) -> StockData:
        """
        gets the bid, ask, last price, and volume of a stock
        """
        MarketData.sign_in()
        stock_data: Any = cast(dict, rh.stocks.get_quotes(sym))[0]
        return StockData(
            stock_data["ask_price"],
            stock_data["bid_price"],
            rh.stocks.get_latest_price(sym)[0],
            cast(dict, rh.stocks.get_fundamentals(sym, info="volume"))[0],
        )

    @staticmethod
    def get_option_data(option: OptionOrder) -> OptionData:
        """
        gets bid, ask, last, price, volatility, greeks, underlying price, and in the money status of an option
        """
        MarketData.sign_in()
        if option.sym == "SPX":
            return NULL_OPTION_DATA
        option_data: list = cast(
            list,
            rh.find_options_by_expiration_and_strike(
                option.sym,
                option.expiration,
                str(option.strike),
                option.option_type.value,
            ),
        )
        data = option_data[0]
        return OptionData(
            data["ask_price"],
            data["bid_price"],
            data["last_trade_price"],
            data["volume"],
            data["implied_volatility"],
            data["delta"],
            data["theta"],
            data["gamma"],
            data["vega"],
            data["rho"],
            None,  # (RH does not provide underlying price)
            None,  # (RH does not provide in the money status)
        )


if __name__ == "__main__":
    from brokers import robinhood

    r = Robinhood(Path(""), BrokerNames.RH)
    r.login()
    res = MarketData.get_option_data(parse_option_string("SPX-Call-5400.00-05/24/2024"))
    print(res)
