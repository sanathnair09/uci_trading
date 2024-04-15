from brokers.trading import AutomatedTrading
from utils.report.report import ActionType
from utils.util import parse_option_string


if __name__ == "__main__":
    """
    stock market hours (PST): 6:30 - 1:00
    """
    # trader = AutomatedTrading(
    #     time_between_buy_and_sell=7, time_between_groups=3, enable_stdout=True
    # )
    # trader.start()
    # trader.sell_leftover_positions()
    # trader.manual_override([
    # ], ActionType.CLOSE)
    AutomatedTrading.generate_report()
