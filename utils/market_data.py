from datetime import datetime

import tda.auth
from loguru import logger

from brokers import TD_KEY, TD_TOKEN_PATH
from utils.broker import OptionOrder
from utils.report.report import (
    NULL_OPTION_DATA,
    OptionData,
    OptionType,
    OrderType,
    StockData,
)
from utils.util import calculate_num_stocks_to_buy, parse_option_string


class MarketData:
    """
    Uses TD Ameritrade API to get stock and option data
    """

    @staticmethod
    def validate_stock(sym: str):
        """
        checks if symbol is valid
        """
        client = tda.auth.client_from_token_file(TD_TOKEN_PATH, TD_KEY)
        res = client.get_quotes(sym).json()
        valid = sym in res and res[sym]["description"] != "Symbol not found"
        if not valid:
            logger.error(f"{sym} not valid")
        return valid

    @staticmethod
    def get_stock_amount(sym: str) -> tuple[int, float]:
        """
        calculates the quantity of stocks needed to buy 100 shares at the current price
        :returns (quantity, price)
        """
        client = tda.auth.client_from_token_file(TD_TOKEN_PATH, TD_KEY)
        price = client.get_quotes(sym).json()[sym]["lastPrice"]
        return calculate_num_stocks_to_buy(100, price), price

    @staticmethod
    def get_stock_data(sym: str) -> StockData:
        """
        gets the bid, ask, last price, and volume of a stock
        """
        client = tda.auth.client_from_token_file(TD_TOKEN_PATH, TD_KEY)
        stock_data = client.get_quotes(sym).json()[sym]
        return StockData(
            stock_data["askPrice"],
            stock_data["bidPrice"],
            stock_data["lastPrice"],
            stock_data["totalVolume"],
        )

    @staticmethod
    def get_option_data(option: OptionOrder) -> OptionData:
        """
        gets bid, ask, last, price, volatility, greeks, underlying price, and in the money status of an option
        """
        client = tda.auth.client_from_token_file(TD_TOKEN_PATH, TD_KEY)
        contract_type = (
            tda.client.Client.Options.ContractType.CALL
            if option.option_type == OptionType.CALL
            else tda.client.Client.Options.ContractType.PUT
        )
        date = datetime.strptime(option.expiration, "%Y-%m-%d")
        option_data = client.get_option_chain(
            symbol=option.sym,
            contract_type=contract_type,
            strategy=tda.client.Client.Options.Strategy.SINGLE,
            strike=float(option.strike),
            from_date=date,
            to_date=date,
        ).json()
        if option.option_type == OptionType.CALL:
            possibilities = option_data["callExpDateMap"]
        else:
            possibilities = option_data["putExpDateMap"]
        for keys in possibilities:
            for key in possibilities[keys]:
                if float(key) == float(option.strike):
                    return OptionData(
                        possibilities[keys][key][0]["ask"],
                        possibilities[keys][key][0]["bid"],
                        possibilities[keys][key][0]["last"],
                        possibilities[keys][key][0]["totalVolume"],
                        possibilities[keys][key][0]["volatility"],
                        possibilities[keys][key][0]["delta"],
                        possibilities[keys][key][0]["theta"],
                        possibilities[keys][key][0]["gamma"],
                        possibilities[keys][key][0]["vega"],
                        possibilities[keys][key][0]["rho"],
                        round(option_data["underlyingPrice"], 4),
                        possibilities[keys][key][0]["inTheMoney"],
                    )
        return NULL_OPTION_DATA


if __name__ == "__main__":
    pass
