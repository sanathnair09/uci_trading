import datetime
import random
import time
from pathlib import Path
from pyexpat import ExpatError

import schedule
from loguru import logger

from brokers import TDAmeritrade, Robinhood, ETrade, Schwab, Fidelity, IBKR
from utils.debugger import init_logging
from utils.misc import get_program_data, update_program_data, reset_program_data
from utils.post_processing import PostProcessing
from utils.report import BrokerNames


PROGRAM_INFO_FILE_PATH = "previous_program_info.json"
PROGRAM_INFO_KEYS = ["PREVIOUS_STOCK_NAME", "STATUS", "FAILURE_LOG",
                     "FAILURE_COUNT", "CURRENTLY_TRADING_STOCKS", "FIRST_RUN"]

STOCK_LIST = [  # TODO: possible optimization with diff data structure
    'UNF', 'WH', 'ODFL', 'NOTV', 'GRWG', 'RAPT', 'WTFC', 'CAPR', 'XOM', 'OPRT', 'BYN',  # 10
    'SHLS', 'AGL', 'BATL', 'PRTK', 'HEAR', 'SCHL', 'IFF', 'EDUC', 'AAP', 'PANW',  # 20
    'TRV', 'AMTX', 'HONE', 'AMTB', 'CVCO', 'CAL', 'GLT', 'NVDA', 'HEI', 'DUNE',  # 30
    'OKE', 'BCC', 'BV', 'PRTH', 'NOV', 'ROOT', 'TSLA', 'MICS', 'PVH', 'CSX',  # 40
    'CTMX', 'NETC', 'NXTC', 'DTOC', 'OLMA', 'POWW', 'INBX', 'W', 'PCYG', 'GO',  # 50 NGC
    'ALXO', 'ZUMZ', 'ENER', 'ADRT', 'CRS', 'WRB', 'RAMP', 'CVLY', 'IMNM', 'EWTX',  # 60 CELC
    'V', 'EBIX', 'INZY', 'BAC', 'DISH', 'PFMT', 'NNBR', 'MCW', 'RDI', 'DWAC',  # 70
    'CVLT', 'RAVE', 'LASE', 'OXM', 'APT', 'ASB', 'MSI', 'SNSE', 'ANIP', 'BBSI',  # 80 TETC
    'VNDA', 'TDG', 'ICAD', 'LXRX', 'EW', 'AMP', 'MODN', 'NRG', 'FRBA', 'GIS',  # 90
    'SCKT', 'AMC', 'KNDI', 'ATRA', 'KVSA', 'AVO', 'SMAP', 'PACK', 'NTAP', 'PLPC',  # 100 AAWW
    'GOOG', 'RM', 'APLS', 'ICCC', 'PROV', 'GEVO', 'RWOD', 'WMPN', 'AWR', 'DCTH',  # 110
    'SXI', 'DHIL', 'CDNA', 'MMI', 'CTIB', 'GBCI', 'AAPL', 'SSNC', 'TCRX', 'OPK',  # 120
    'FFIV', 'AGX', 'PTLO', 'LUNG', 'CPK', 'TACT', 'SIX', 'GS', 'PXLW', 'GWRE',  # 130 KNBE
    'WBS', 'ALB', 'CCVI'  # 133 'BYN' moved
]
STOCK_LIST_LEN = len(STOCK_LIST)


def log_failure(stock, amount, broker):
    curr_time = datetime.datetime.now().strftime("%X:%f")
    update_program_data(PROGRAM_INFO_FILE_PATH, "FAILURE_LOG", (stock, amount, curr_time, broker),
                        is_list = True)
    update_program_data(PROGRAM_INFO_FILE_PATH, "FAILURE_COUNT",
                        get_program_data(PROGRAM_INFO_FILE_PATH, "FAILURE_COUNT") + 1)


def buy_across_brokers(brokers, stock_list):
    update_program_data(PROGRAM_INFO_FILE_PATH, "STATUS", "Buy")
    stock_list = [(TDAmeritrade.get_stock_amount(sym), sym) for sym in stock_list]
    update_program_data(PROGRAM_INFO_FILE_PATH, "CURRENTLY_TRADING_STOCKS", stock_list)
    print(f"Currently Buying: {str(stock_list)}")
    for amount, stock in stock_list:
        for group in brokers:
            for broker in group:
                try:
                    broker.buy(stock, amount)
                    broker.save_report()
                except Exception as e:
                    print(f"{broker.name()} Error buying {amount} '{stock}' stocks: {e}")
                    log_failure(stock, amount, broker.name())
        update_program_data(PROGRAM_INFO_FILE_PATH, "PREVIOUS_STOCK_NAME", stock)
    print("Done Buying...")


def sell_across_brokers(brokers, stock_list):
    update_program_data(PROGRAM_INFO_FILE_PATH, "STATUS", "Sell")
    stock_list = get_program_data(PROGRAM_INFO_FILE_PATH, "CURRENTLY_TRADING_STOCKS")
    print(f"Currently Selling: {str(stock_list)}")
    for amount, stock in stock_list:
        for group in brokers:
            for broker in group:
                try:
                    broker.sell(stock, amount)
                    broker.save_report()
                except Exception as e:
                    print(f"{broker.name()} Error selling {amount} '{stock}' stocks: {e}")
                    log_failure(stock, amount, broker.name())
        update_program_data(PROGRAM_INFO_FILE_PATH, "PREVIOUS_STOCK_NAME", stock)
    print("Done Selling...")


def setup():
    print("Running pre-trade setup...")
    program_info = Path(PROGRAM_INFO_FILE_PATH)
    if not program_info.exists():
        program_info.touch()
        program_info.write_text("{\n}")
    for key in PROGRAM_INFO_KEYS:
        try:
            get_program_data(PROGRAM_INFO_FILE_PATH, key)
        except KeyError:
            if key == PROGRAM_INFO_KEYS[3]:
                update_program_data(PROGRAM_INFO_FILE_PATH, key, 0)
            elif key == PROGRAM_INFO_KEYS[0]:
                update_program_data(PROGRAM_INFO_FILE_PATH, key, STOCK_LIST[0])
            elif key == PROGRAM_INFO_KEYS[1]:
                update_program_data(PROGRAM_INFO_FILE_PATH, key, "Buy")
            elif key == PROGRAM_INFO_KEYS[2]:
                update_program_data(PROGRAM_INFO_FILE_PATH, key, [])
            elif key == PROGRAM_INFO_KEYS[4]:
                update_program_data(PROGRAM_INFO_FILE_PATH, key, [])
            elif key == PROGRAM_INFO_KEYS[5]:
                update_program_data(PROGRAM_INFO_FILE_PATH, key, True)
    if get_program_data(PROGRAM_INFO_FILE_PATH, "FIRST_RUN"):
        reset_program_data(PROGRAM_INFO_FILE_PATH,
                           [
                               ("FAILURE_LOG", []),
                               ("FAILURE_COUNT", 0),
                               ("STATUS", "Buy"),
                               ("CURRENTLY_TRADING_STOCKS", []),
                           ])
        update_program_data(PROGRAM_INFO_FILE_PATH, "FIRST_RUN", False)

    # TODO: if crashed on sell resume by selling

    print("Creating report file...")
    report_file = Path(f"reports/original/report_{datetime.datetime.now().strftime('%m_%d')}.csv")
    print("Finished creating report file...")

    print("Finished pre-trade setup...")

    return report_file


def automated_trading(start_time: str, time_between_buy_and_sell: float,
                      time_between_groups: float):
    report_file = setup()

    # might have to keep schwab at end for selenium reasons
    brokers = [
        [TDAmeritrade(report_file, BrokerNames.TD), ],
        [Robinhood(report_file, BrokerNames.RH), ],
        [
            # ETrade(report_file, BrokerNames.ET),
            ETrade(report_file, BrokerNames.E2),
        ],
        [
            Fidelity(report_file, BrokerNames.FD),
        ],
        [
            IBKR(report_file, BrokerNames.IF),
        ],
        [
            Schwab(report_file, BrokerNames.SB)
        ],
    ]

    for group in brokers:
        for broker in group:
            broker.login()

    print("Finished Logging into all brokers...")

    last_stock_name = get_program_data(PROGRAM_INFO_FILE_PATH, "PREVIOUS_STOCK_NAME")
    current_idx = (STOCK_LIST.index(
        last_stock_name) + 1) % STOCK_LIST_LEN
    # goal_idx = (current_idx - 1) % STOCK_LIST_LEN # previous stock
    temp_counter = 20
    print(f"Curr Idx: {current_idx} {STOCK_LIST[current_idx]}")
    # print(f"Goal Idx: {goal_idx} {STOCK_LIST[goal_idx]}")

    buy_time = datetime.datetime.strptime(start_time, "%H:%M")
    sell_time = buy_time + datetime.timedelta(minutes = time_between_buy_and_sell)

    while temp_counter > 0:  # FIXME: possible inf loop
        stock_list = STOCK_LIST[current_idx:current_idx + 4]  # chooses next 4 stocks to trade
        print(f"Buying at: {buy_time.strftime('%H:%M')}")
        print(f"Selling at: {sell_time.strftime('%H:%M')}")

        random.shuffle(brokers)
        for group in brokers:
            random.shuffle(group)

        schedule.every().day.at(buy_time.strftime("%H:%M")).do(buy_across_brokers,
                                                               brokers = brokers,
                                                               stock_list = stock_list)
        schedule.every().day.at(sell_time.strftime("%H:%M")).do(sell_across_brokers,
                                                                brokers = brokers,
                                                                stock_list = stock_list)

        buy_time = sell_time + datetime.timedelta(minutes = time_between_groups)
        sell_time = buy_time + datetime.timedelta(minutes = time_between_buy_and_sell)
        current_idx = (current_idx + 5) % STOCK_LIST_LEN
        temp_counter -= 1

    print(f"Curr Idx: {current_idx} {STOCK_LIST[current_idx]}")
    # print(f"Goal Idx: {goal_idx} {STOCK_LIST[goal_idx]}")

    while True:
        schedule.run_pending()
        time.sleep(1)


def manual_override(stock_list):
    """in the event the program crashes while selling and couldn't sell you can manually feed in the information and sell the stocks"""
    report_file = Path(
        "reports/original/report_{0}.csv".format(datetime.datetime.now().strftime("%m_%d")))

    brokers = [
        # TDAmeritrade(report_file, BrokerNames.TD),
        # Robinhood(report_file, BrokerNames.RH),
        # ETrade(report_file, BrokerNames.ET),
        # ETrade(report_file, BrokerNames.E2),
        # Fidelity(report_file, BrokerNames.FD),
        IBKR(report_file, BrokerNames.IF),
        # Schwab(report_file, BrokerNames.SB)
    ]

    for broker in brokers:
        broker.login()

    for amount, stock in stock_list:
        for broker in brokers:
            try:
                broker.sell(stock, amount)
                broker.save_report()
            except Exception as e:
                print(f"Error selling {amount} '{stock}' stocks: {e}")


def sell_leftover_positions():
    report_file = Path(
        "reports/original/report_{0}.csv".format(datetime.datetime.now().strftime("%m_%d")))

    brokers = [
        [TDAmeritrade(report_file, BrokerNames.TD), ],
        [Robinhood(report_file, BrokerNames.RH), ],
        [
            ETrade(report_file, BrokerNames.ET),
            ETrade(report_file, BrokerNames.E2),
        ],
        # [Fidelity(report_file, BrokerNames.FD), ],
        # [IBKR(report_file, BrokerNames.IB),],
        # [Schwab(report_file, BrokerNames.SB)],
    ]

    for group in brokers:
        for broker in group:
            broker.login()

    for group in brokers:
        for broker in group:
            try:
                leftover = broker.get_current_positions()
                to_sell = [(sym, amount) for sym, amount in leftover if sym in STOCK_LIST]
                print(broker.name(), to_sell)
                for sym, amount in to_sell:
                    broker.sell(sym, amount)
                    broker.save_report()
            except ExpatError:
                print(broker.name(), "No positions")
            except Exception as e:
                logger.error(e)


if __name__ == "__main__":
    """
    stock market hours (PST): 6:30 - 1:00
    """
    init_logging()
    # TODO: get stock status at beginning of day to check at end of day
    # automated_trading("10:20", 7, 3)
    # sell_leftover_positions()
    # manual_override([
    # ])
    processor = PostProcessing()
    processor.generate_report(f"reports/original/report_{datetime.datetime.now().strftime('%m_%d')}.csv")
    pass
