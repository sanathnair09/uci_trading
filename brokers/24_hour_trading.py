import random
import time
from datetime import datetime, timedelta
from pyexpat import ExpatError
from typing import Any, Optional, Union, cast
from utils.report.report import OptionType, OrderType
from pathlib import Path
import traceback


import schedule
from loguru import logger
from brokers import BASE_PATH

from brokers import (
    BASE_PATH,
    # Robinhood,
    Robinhood2,
    Fidelity,
    ETrade,
    Schwab,
    Vanguard,
    IBKR,
)
from utils.broker import Broker, OptionOrder, StockOrder
from utils.market_data import MarketData
from utils.program_manager import ProgramManager, SYM_LIST_LEN, SYM_LIST
from utils.TwentyFourHourManager import TwentyFourHourManager
from utils.report.post_processing import PostProcessing
from utils.report.report import ActionType, BrokerNames
from utils.util import (
    format_list_of_orders,
    parse_option_list,
    parse_stock_list,
    process_option_input,
)


# EQUITY_BROKERS = ["TD", "RH", "E2", "FD", "SB"]
# EQUITY_BROKERS = ["RH", "E2", "FD", "SB"]


EQUITY_BROKERS = ["E2", "FD", "SB"]
# EQUITY_BROKERS = ["E2", "SB"]


# FRAC_BROKERS = ["FD", "IF", "RH"]
# FRAC_BROKERS = ["FD", "RH"]
FRAC_BROKERS = ["FD"]
# OPTN_BROKERS = ["TD", "RH", "E2", "FD", "SB", "VD"]
OPTN_BROKERS = ["RH", "E2", "FD", "SB", "IF", "VD"]

TWENTY_FOUR_REPORT_COLUMNS = [
    'Date', 'Program Submitted', 'Broker Executed', 'Symbol', 'Action', 'Size', 'Broker', 'Price', 'Spread', 'Ask Price', 'Bid_Price', 'Limit_Price'
    ]


class TwentyFourHourTrading:
    def __init__(self):
        logger.info("Beginning 24 Hour Trading")


        self._manager = ProgramManager(enable_stdout=True)
        self._24_hour_manager = TwentyFourHourManager()

        report_file, option_report_file = (
            self._manager.report_file,
            self._manager.option_report_file,
        )

        self._brokers: list[Broker] = [
            # IBKR(report_file, BrokerNames.IF, option_report_file),
            # Fidelity(report_file, BrokerNames.FD, option_report_file),
            # ETrade(report_file, BrokerNames.E2, option_report_file),
            # Schwab(report_file, BrokerNames.SB, option_report_file),
            Robinhood2(report_file, BrokerNames.RH, option_report_file),
            # Vanguard(report_file, BrokerNames.VD, option_report_file),          # Vanguard only for options
        ]

        self.create_report_file()

        # Old groups when we were using 6:
        # self.group_one = ['AMZN', 'BBY', 'AXP']
        # self.group_two = ['GPC', 'AAPL', 'HE', 'NTES']
        # self.group_three = ['CPB', 'CUBE', 'FBTC']
        # self.group_four = ['EOG', 'NCLH', 'HES', 'QQQ']
        # self.group_five = ['VZ', 'EQT', 'GME']
        # self.group_six = ['LUV', 'YINN', 'NVDA', 'ASO']

        # self._symbol_list = [self.group_one, self.group_two, self.group_three,
        #         self.group_four, self.group_five, self.group_six]

        self.group_one = ['HE', 'EOG']
        self.group_two = ['LUV', 'HES', 'NTES']
        self.group_three = ['GPC', 'NVDA']
        self.group_four = ['NCLH', 'CUBE', 'VZ']
        self.group_five = ['AAPL', 'SPY', 'YINN']
        self.group_six = ['ASO', 'AMZN', 'GME']
        self.group_seven = ['QQQ', 'CPB']
        self.group_eight = ['EQT', 'FBTC']
        self.group_nine = ['AXP', 'BBY']

        self._symbol_list = [self.group_one, self.group_two, self.group_three,
                             self.group_four, self.group_five, self.group_six, 
                             self.group_seven, self.group_eight, self.group_nine]
        

        self._login_all()


    def _login_all(self) -> None:
        for broker in self._brokers:
            broker.login()
        logger.info("Finished Logging into all brokers...")


    '''
    Creates the report file
    '''
    def create_report_file(self) -> None:

        date = datetime.now().strftime("%m_%d")
        report_file = BASE_PATH / f"reports/24_hour/24_report_{date}.csv"

        def create_file(file, report_columns: list[str], msg: str) -> None:
            if not file.exists():
                logger.info(f"Creating {msg} file...")
                with open(file, "w") as f:
                    f.write(",".join(report_columns) + "\n")
                    logger.info(f"Finished creating {msg} file...")

        create_file(report_file, TWENTY_FOUR_REPORT_COLUMNS, "24 Hour")


    '''
    Shifts the group at a certain time each day
    '''
    def shift_groups(self) -> None:
        # Format of group assignment:         group_assignment = [1, 1, 1, 2, 3, 4, 5, 5, 6, 7, 8, 9,
        #                                                           1, 2, 3, 4, 4, 5, 6, 7, 8, 8, 9,
        #                                                           9, 9]
        group_assignment = self._24_hour_manager.get("GROUP_ASSIGNMENT")

        # increment all group numbers
        # CHANGE BACK TO 9 WHEN YOU GO BACK TO 9 GROUPS
        for i in range(len(group_assignment)):
            if group_assignment[i] == 9:
                group_assignment[i] = 1
            else:
                group_assignment[i] += 1

        # print(group_assignment)
        
        # set the new group assignment
        self._24_hour_manager.set("GROUP_ASSIGNMENT", group_assignment)

        logger.info("Shifted group assignments")

            

    '''
    Takes symbol list and randomly splits into two different lists
    '''
    def _split_symbols(self) -> None:
 
        # get copy of symbol list
        shuffled_list = self._symbol_list[:]

        # Shuffle the copy randomly
        random.shuffle(shuffled_list)

        # Split the shuffled list evenly
        midpoint = len(shuffled_list) // 2
        self._part_one_symbol_list = shuffled_list[:midpoint]
        self._part_two_symbol_list = shuffled_list[midpoint:]


    '''
    Starts 24 hour trading procedure
    '''
    def start(self) -> None:

        # Schedule the trading for the day
        self._schedule()


        # for job in schedule.jobs:
        #     print(f"{job.next_run} {job.job_func.__name__}")

        # Runs the program while there are more jobs in the schedule
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(e)
                traceback.print_exc()


    '''
    Schedules the trading thats going to be done for the day
    '''
    def _schedule(self) -> None:
        logger.info("Scheduling Times")

        # trade_all_symbols_times = ["12:30", "12:50", "13:10", "14:10", "15:10", "16:10", "16:50",
        #                            "17:10", "18:10", "19:10", "20:10", "21:10", "22:10", "23:10",
        #                            "00:10", "00:40", "01:10", "02:10", "03:10", "04:10", "04:50",
        #                            "05:10","06:10", "06:40", "07:00"]
        
        # adding 6:20 AM EST as a time to investigate RH missing all the 6:10 AM trades
        trade_all_symbols_times = ["12:30", "12:50", "13:10", "14:10", "15:10", "16:10", "16:50",
                            "17:10", "18:10", "19:10", "20:10", "21:10", "22:10", "23:10",
                            "00:10", "00:40", "01:10", "02:10", "03:05", "03:10", "04:10", "04:50",
                            "05:10","06:10", "06:40", "07:00"]

        # schedule trades that sell all symbols
        for i, time in enumerate(trade_all_symbols_times):
            schedule.every().day.at(time).do(self.trade_symbols_across_brokers, sym_list=self._symbol_list, index=i)

        # self._brokers[0].buy_and_sell_immediately("MA")
        # schedule the sell leftovers method for ibkr every 2 minutes
        # schedule.every(1).minutes.do(self._brokers[0].sell_later_filled_orders)

        # schedule creation of report file and shuffling of symbols
        schedule.every().day.at("00:01").do(self.create_report_file)
        schedule.every().day.at("07:00").do(self.sell_leftover_positions_across_brokers)
        schedule.every().day.at("12:29:45").do(self.shift_groups)          # at 12:25, shift the group assignments

        logger.info("Done scheduling")


    '''
    Immediately buys and sells each symbol across every broker
    '''
    def trade_symbols_across_brokers(self, sym_list, index) -> None:
        from datetime import time
        
        # Get group assignemnts from manager
        # Format of group assignment:         group_assignment = [1, 1, 1, 2, 3, 4, 5, 5, 6, 7, 8, 9,
        #                                                           1, 2, 3, 4, 4, 5, 6, 7, 8, 8, 9,
        #                                                           9, 9]
        group_assignment = self._24_hour_manager.get("GROUP_ASSIGNMENT")
        group_index = group_assignment[index]
        curr_sym_list = self._symbol_list[group_index-1]

        # curr_sym_list = ["AMZN", "AAPL"]

        # Run the task only if it's Sunday (6) through Friday (4)
        current_day = datetime.now().weekday()
        if current_day not in {6, 0, 1, 2, 3, 4}:
            return schedule.cancel_job
        
        # if it's sunday before 5 PM, don't do anything ( program should make first trade at 5:10 PM Sunday )
        if current_day == 6 and datetime.now().time() < time(17, 0):
            return

        # if it's friday after 5, don't do anything (program should be stopped)
        if current_day == 4 and datetime.now().time() > time(17, 0):
            return

        logger.info(f"\n\nCurrently Group {group_index}: {curr_sym_list}")

        # change sym list to have (sym, quantity)
        # update sym list to add the stocks whos quantity will be greater than 1
        # then execute those trades
        # will have to modify our functions slightly

        # execute trades
        for sym in curr_sym_list:
            for broker in random.sample(self._brokers, len(self._brokers)):
                try:
                    broker.buy_and_sell_immediately(sym)
                    # broker.buy_and_sell_immediately('AMZN')
                except Exception as e:
                    logger.error(f"Error trading {sym} on {broker._broker_name}")
                    # add line to add rejected order to report here ?
                    logger.error(e)
                    

        # Added this line just in case order gets immediately filled on ibkr
        # try:
        #     self._brokers[0].sell_later_filled_orders()
        # except Exception as e:
        #     logger.error(f"Error selling leftovers on IBKR")


        # logger message
        logger.info("DONE BUYING AND SELLING")


    '''
    Sells any open positions across all brokers
    '''
    def sell_leftover_positions_across_brokers(self):
        

        # broker[0].sell_24_hour_leftover_positions()

        # VERIFY THIS WORKS!
        for broker in self._brokers:
            try:
                broker.sell_24_hour_leftover_positions()
                # positions, option_position = broker.get_current_positions()
                # if len(positions) == 0:
                #     continue

                # # if (type(positions[0]) == StockOrder):
                # #     positions = [order.sym for order in positions]

                # print(broker.name(), str(positions))

                # for stock_order in positions:
                #     broker.sell_limit(stock_order)


            except Exception as e:
                logger.error(e)

        logger.info("Sold leftovers on all brokers")
        return
    



    ''' 
    Sells any leftover positions
    Not sure how this will work with old script?
    '''
    def sell_leftover_positions(self) -> None:

        for broker in self._brokers:
            try:
                positions, option_position = broker.get_current_positions()
                print(broker.name(), str(positions), str(option_position))

                for stock_order in positions:
                    broker.sell(stock_order)

                for option_order in option_position:
                    broker.sell_option(option_order)

            except ExpatError:
                print(broker.name(), "No positions")
            except Exception as e:
                logger.error(e)


    def _choose_brokers(self, brokers: Optional[list[str]]) -> list[Broker]:
        """
        :param `brokers` list of broker names to enable (if none returns all)
        :returns all the brokers that are enabled
        """
        selected: list[Broker] = []
        if not brokers:
            selected = self._brokers.copy()  # to prevent modifying original list
        else:
            for broker in self._brokers:
                for item in brokers:
                    if broker.name() == item:
                        selected.append(broker)

        random.shuffle(selected)
        return selected


    @staticmethod
    def generate_reports(
        dates: list[str], equity: bool = True, option: bool = True, *, version: int = 0
    ) -> None:
        processor = PostProcessing(version)
        # processor.generate_report(f"reports/original/report_xx_xx.csv")
        for date in dates:
            equity_path = BASE_PATH / f"reports/original/report_{date}.csv"
            option_path = BASE_PATH / f"reports/original/option_report_{date}.csv"
            if equity:
                processor.generate_report(str(equity_path))
            if option:
                processor.generate_report(str(option_path), True)


if __name__ == "__main__":
    trader = TwentyFourHourTrading()

    trade_all_symbols_times = ["12:30", "12:50", "13:10", "14:10", "15:10", "16:10", "16:50",
                    "17:10", "18:10", "19:10", "20:10", "21:10", "22:10", "23:10",
                    "00:10", "00:40", "01:10", "02:10", "03:05", "03:10", "04:10", "04:50",
                    "05:10","06:10", "06:40", "07:00"]
    
    # trader.shift_groups()
    trader.start()
    # trader.sell_leftover_positions_across_brokers()


    # trader._split_symbols()
    # print(datetime.now().weekday())
    # pass
