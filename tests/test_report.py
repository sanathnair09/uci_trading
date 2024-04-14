from utils.report.report import (
    ActionType,
    BrokerNames,
    OptionData,
    OptionType,
    OrderType,
    ReportEntry,
    StockData,
)


class TestReport:
    def test_action_type(self):
        assert ActionType.BUY.value == "Buy"
        assert ActionType.SELL.value == "Sell"
        assert ActionType.OPEN.value == "open"
        assert ActionType.CLOSE.value == "close"

    def test_option_type(self):
        assert OptionType.CALL.value == "call"
        assert OptionType.PUT.value == "put"
    
    def test_order_type(self):
        assert OrderType.MARKET.value == "Market"
        assert OrderType.LIMIT.value == "Limit"

    def test_broker_names(self):
        assert BrokerNames.TD.value == "TD"
        assert BrokerNames.RH.value == "RH"
        assert BrokerNames.ET.value == "ET"
        assert BrokerNames.E2.value == "E2"
        assert BrokerNames.SB.value == "SB"
        assert BrokerNames.FD.value == "FD"
        assert BrokerNames.IF.value == "IF"
        assert BrokerNames.VD.value == "VD"

    def test_init_stock_data(self):
        stock_data = StockData(1.2, 1.3, 10, 100)
        assert stock_data.ask == 1.2
        assert stock_data.bid == 1.3
        assert stock_data.quote == 10
        assert stock_data.volume == 100
        assert str(stock_data) == "1.2,1.3,10,100"

    def test_init_option_data(self):
        option_data = OptionData(
            1.2, 1.3, 10, 100, 0.5, 0.6, 0.7, 0.8, 0.9, 0.10, 0.11, True
        )
        assert option_data.ask == 1.2
        assert option_data.bid == 1.3
        assert option_data.quote == 10
        assert option_data.volume == 100
        assert option_data.volatility == 0.5
        assert option_data.delta == 0.6
        assert option_data.theta == 0.7
        assert option_data.gamma == 0.8
        assert option_data.vega == 0.9
        assert option_data.rho == 0.10
        assert option_data.underlying_price == 0.11
        assert option_data.in_the_money is True
        assert str(option_data) == "1.2,1.3,10,100,0.5,0.6,0.7,0.8,0.9,0.1,0.11,True"

    def test_init_report_entry(self):
        entry = ReportEntry(
            "10:00:00",
            "10:01:00",
            "10:00:30",
            "AAPL",
            ActionType.BUY,
            10,
            172.50,
            1750.00,
            StockData(1.2, 1.3, 10, 100),
            StockData(1.2, 1.3, 10, 100),
            OrderType.MARKET,
            False,
            "1234",
            "5678",
            BrokerNames.TD,
        )
        assert entry.program_submitted == "10:00:00"
        assert entry.program_executed == "10:01:00"
        assert entry.broker_executed == "10:00:30"
        assert entry.sym == "AAPL"
        assert entry.action == ActionType.BUY
        assert entry.quantity == 10
        assert entry.price == 172.50
        assert entry.dollar_amt == 1750.00
        assert entry.order_type == OrderType.MARKET
        assert entry.split is False
        assert entry.order_id == "1234"
        assert entry.activity_id == "5678"
        assert entry.broker == BrokerNames.TD
