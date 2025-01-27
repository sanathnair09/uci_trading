from brokers.trading import AutomatedTrading
from utils.broker import OptionOrder, StockOrder
from utils.report.report import ActionType, OptionType, OrderType
from utils.util import parse_option_string
from datetime import datetime


'''
At end of day after selling leftover positions and
making sure accounts are 0, run fidelity.py

'''
if __name__ == "__main__":
    """
    stock market hours (PST): 6:30 - 1:00
    """
    # print('yo')
    
    trader = AutomatedTrading(
        time_between_buy_and_sell=7, time_between_groups=3, enable_stdout=True
    )

    # trader.start()
    trader.sell_leftover_positions()

    # USE THIS TO MANUALLY SELL POSITIONS:
    # trader.manual_override(
    #     [
    #         # parse_option_string("")

    #         # FORMAT: StockOrder("STOCK_NAME", STOCK_QUANTITY)

    #         # StockOrder("CRS", 1.1),
    #         StockOrder("DOUG", 57),
    #         # StockOrder("IMNM", 10),
    #         # StockOrder("NOTV", 23),
    #         # StockOrder("VNDA", 23),
    #         # StockOrder("MKTX", 1.1),
    #         # StockOrder("PACK", 15),
    #         # StockOrder("RAMP", 0.1),
    #         # StockOrder("RDI", 69),
    #         # StockOrder("SSNC", 1.1),
    #         # StockOrder("WBS", 0.25)
    #     ],
    #     ActionType.SELL,
    # )

    # # manual override format:
    # # trader.manual_override(
    # #     [
    # #         OptionOrder(sym='F', option_type=OptionType.CALL, strike='10.50', expiration='2024-11-08', order_type=OrderType.MARKET, quantity=1)
    # #     ],
    # #     ActionType.CLOSE,
    # # )


    # AutomatedTrading.generate_reports(
    #     ["01_23", "01_24"],            # format: ["08_23"]
    #     equity=True,
    #     option=True,
    # )
