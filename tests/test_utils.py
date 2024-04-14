from unittest.mock import patch
from utils.report.report import OptionType, OrderType
from utils.util import (
    calculate_num_stocks_to_buy,
    convert_to_float,
    parse_option_string,
    process_option_input,
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

    # @patch("builtins.input", return_value="")
    def test_process_empty_option_input(self, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda _: "")
        res = process_option_input()
        assert len(res) == 0

    # @patch("builtins.input", return_value="AAPL-Call-100-01/01/2022")
    def test_process_option_input(self, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda _: "AAPL-Call-100-01/01/2022")
        res = process_option_input()
        assert len(res) == 1
        option = res[0]
        assert option is not None
        assert option.sym == "AAPL"
        assert option.order_type == OrderType.MARKET
        assert option.option_type == OptionType.CALL
        assert option.strike == "100"
        assert option.expiration == "2022-01-01"
