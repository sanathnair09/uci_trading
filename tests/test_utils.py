from unittest.mock import patch
from utils.broker import OptionOrder, StockOrder
from utils.report.report import OptionType, OrderType
from utils.util import (
    calculate_num_stocks_to_buy,
    convert_to_float,
    process_option_input,
    parse_option_string,
    parse_option_list,
    format_list_of_orders,
    parse_stock_string,
    parse_stock_list,
    convert_date,
)


class TestUtils:
    def test_calculate_num_stocks_to_buy(self):
        DOLLAR_AMT = 100
        assert calculate_num_stocks_to_buy(DOLLAR_AMT, 100) == 1
        assert calculate_num_stocks_to_buy(DOLLAR_AMT, 50) == 2
        assert calculate_num_stocks_to_buy(DOLLAR_AMT, 33.33) == 3
        assert calculate_num_stocks_to_buy(DOLLAR_AMT, 500) == 1

    def test_convert_to_float(self):
        assert convert_to_float("100") == 100.0
        assert convert_to_float("100.0") == 100.0
        assert convert_to_float("100.0") == 100.0
        assert convert_to_float("") == None

    def test_parse_call_option_string_nondecimal_strike(self):
        option = "AAPL-Call-100-01/01/2022"
        res = parse_option_string(option)
        assert res is not None
        assert res.sym == "AAPL"
        assert res.order_type == OrderType.MARKET
        assert res.option_type == OptionType.CALL
        assert res.strike == "100"
        assert res.expiration == "2022-01-01"

    def test_parse_call_option_string_decimal_strike_with_trailing_zero(self):
        option = "AAPL-Call-100.50-01/01/2022"
        res = parse_option_string(option)
        assert res is not None
        assert res.sym == "AAPL"
        assert res.order_type == OrderType.MARKET
        assert res.option_type == OptionType.CALL
        assert res.strike == "100.50"
        assert res.expiration == "2022-01-01"

    def test_parse_call_option_string_decimal_strike(self):
        option = "AAPL-Call-100.55-01/01/2022"
        res = parse_option_string(option)
        assert res is not None
        assert res.sym == "AAPL"
        assert res.order_type == OrderType.MARKET
        assert res.option_type == OptionType.CALL
        assert res.strike == "100.55"
        assert res.expiration == "2022-01-01"

    def test_parse_put_option_string_nondecimal_strike(self):
        option = "AAPL-Put-100-01/01/2022"
        res = parse_option_string(option)
        assert res is not None
        assert res.sym == "AAPL"
        assert res.order_type == OrderType.MARKET
        assert res.option_type == OptionType.PUT
        assert res.strike == "100"
        assert res.expiration == "2022-01-01"

    def test_parse_put_option_string_decimal_strike_with_trailing_zero(self):
        option = "AAPL-Put-100.50-01/01/2022"
        res = parse_option_string(option)
        assert res is not None
        assert res.sym == "AAPL"
        assert res.order_type == OrderType.MARKET
        assert res.option_type == OptionType.PUT
        assert res.strike == "100.50"
        assert res.expiration == "2022-01-01"

    def test_parse_put_option_string_decimal_strike(self):
        option = "AAPL-Put-100.55-01/01/2022"
        res = parse_option_string(option)
        assert res is not None
        assert res.sym == "AAPL"
        assert res.order_type == OrderType.MARKET
        assert res.option_type == OptionType.PUT
        assert res.strike == "100.55"
        assert res.expiration == "2022-01-01"

    def test_process_empty_option_input(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        res = process_option_input()
        assert len(res) == 0

    def test_process_option_input(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "AAPL-Call-100-01/01/2022")
        res = process_option_input()
        assert len(res) == 1
        option = res[0]
        assert option is not None
        assert option.sym == "AAPL"
        assert option.order_type == OrderType.MARKET
        assert option.option_type == OptionType.CALL
        assert option.strike == "100"
        assert option.expiration == "2022-01-01"

    def test_format_list_of_orders(self):
        res = format_list_of_orders(
            [StockOrder("AAPL", 1.0, 1.0), StockOrder("MSFT", 1.25, 1)]
        )
        assert res == ["AAPL,1.0,1.0", "MSFT,1.25,1"]

    def test_parse_stock_list(self):
        assert parse_stock_list([]) == []
        res = parse_stock_list(["AAPL,1.0,1.0", "MSFT,1.25,1"])
        assert len(res) == 2
        assert res == [
            StockOrder("AAPL", 1.0, 1.0),
            StockOrder("MSFT", 1.25, 1),
        ]

    def test_parse_option_list(self):
        assert parse_option_list([]) == []
        res = parse_option_list(["AAPL-Call-100-01/01/2022", "MSFT-Put-100-01/01/2022"])
        assert len(res) == 2
        assert res == [
            OptionOrder("AAPL", OptionType.CALL, "100", "2022-01-01", OrderType.MARKET),
            OptionOrder("MSFT", OptionType.PUT, "100", "2022-01-01", OrderType.MARKET),
        ]

    def test_convert_date(self):
        assert convert_date("2022-01-01", "%m/%d/%Y") == "01/01/2022"
        assert convert_date("2022-01-01", "%Y-%m-%d") == "2022-01-01"
