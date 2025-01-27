import random
import time
from datetime import datetime, timedelta, timezone
from pyexpat import ExpatError
from typing import Any, Optional, Union, cast
from utils.report.report import OptionType, OrderType

import schedule
from loguru import logger

from brokers import (
    BASE_PATH,
    Robinhood,
    Fidelity,
    ETrade,
    Schwab,
    Vanguard,
    IBKR,
)
from utils.broker import Broker, OptionOrder, StockOrder
from utils.market_data import MarketData
from utils.program_manager import ProgramManager, SYM_LIST_LEN, SYM_LIST
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


class AutomatedTrading:
    def __init__(
        self,
        *,
        time_between_buy_and_sell: float,
        time_between_groups: float,
        enable_stdout: bool = False,
    ):
        logger.info("Beginning Automated Trading")

        # UNCOMMENT FOR OPTIONS
        # Options stuff:
        self._options_list = process_option_input()
        logger.info("Trading Options: " + str(self._options_list))

        self._time_between_buy_and_sell = time_between_buy_and_sell
        self._time_between_groups = time_between_groups

        self._manager = ProgramManager(enable_stdout=enable_stdout)
        report_file, option_report_file = (
            self._manager.report_file,
            self._manager.option_report_file,
        )

        # if you need to something with only one broker, comment it out here
        self._brokers: list[Broker] = [
            # Fidelity(report_file, BrokerNames.FD, option_report_file),
            # ETrade(report_file, BrokerNames.E2, option_report_file),
            # Schwab(report_file, BrokerNames.SB, option_report_file),
            Robinhood(report_file, BrokerNames.RH, option_report_file),
            # IBKR(report_file, BrokerNames.IF, option_report_file),
            # Vanguard(report_file, BrokerNames.VD, option_report_file),          # Vanguard only for options
        ]

        self._fractionals = [0.1, 0.25, 0.5, 0.75, 0.9]

        self._login_all()

    def _login_all(self) -> None:
        for broker in self._brokers:
            broker.login()
        logger.info("Finished Logging into all brokers...")

    def start(self) -> None:
        '''
        Starts automated trading procedure
        '''
        # Schedule the trading for the day
        # self.schedule_the_schedule()
        self._schedule()

        # Runs the program while there are more jobs in the schedule
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
                if len(schedule.get_jobs()) == 0:
                    logger.info("Finished trading")
                    break
            except Exception as e:
                logger.error(e)



    def _pre_schedule_processing(self) -> tuple[int, int]:
        '''
        Gets the index of SYM list at which we start trading as well as any completed stuff if run
        on same day
        '''

        # program is run on new day
        if self._manager.get("DATE") != datetime.now().strftime("%x"):
            self._manager.set("DATE", datetime.now().strftime("%x"))
            # resuming from previous run
            if self._manager.get("COMPLETED") != SYM_LIST_LEN:
                last_stock_name = self._manager.get("PREVIOUS_STOCK_NAME")
                current_idx = (SYM_LIST.index(last_stock_name) + 1) % SYM_LIST_LEN
            else:  # choose random stock and begin from there
                random_sym = random.choice(SYM_LIST)
                current_idx = SYM_LIST.index(random_sym)
            self._manager.set("COMPLETED", 0)
            self._manager.set("COMPLETED_OPTIONS", 0)
        else:
            last_stock_name = self._manager.get("PREVIOUS_STOCK_NAME")
            current_idx = (SYM_LIST.index(last_stock_name) + 1) % SYM_LIST_LEN

        return current_idx, self._manager.get("COMPLETED_OPTIONS")


    def schedule_the_schedule(self):
        # schedules the schedule method at 6:30 AM
        schedule.every().day.at("06:30").do(self._schedule)

    def _schedule(self) -> None:
        '''
        Schedules the trading thats going to be done for the day
        '''

        current_idx, completed_options = self._pre_schedule_processing()
        print(completed_options)
        # need to subtract in the case when re-running on same day and already completed some trades
        count = SYM_LIST_LEN - self._manager.get("COMPLETED")
        option_idx = completed_options  # needed for array indexing

        OPTN_LIST_LEN = len(self._options_list)                   # UNCOMMENT FOR OPTIONS

        # Latest possible time for trading
        SELL_TIME_LIMIT = datetime.now().replace(
            hour=12, minute=50, second=0, microsecond=0
        )

        # Initialize the FIRST buy and sell time
        buy_time = datetime.now() + timedelta(minutes=1)
        sell_time = buy_time + timedelta(minutes=self._time_between_buy_and_sell)

        # print(count)
        # print(sell_time)
        # print(SELL_TIME_LIMIT)
        # option_idx = 0
        while (count > 0 or option_idx < OPTN_LIST_LEN) and sell_time < SELL_TIME_LIMIT:
            # Chooses next 4 stocks to trade
            sym_list = SYM_LIST[current_idx : current_idx + 4]

            # Added a check to make sure that the SYM is valid
            sym_list = [sym for sym in sym_list if MarketData.validate_stock(sym)]

            # Log the scheddy
            logger.info(sym_list)
            logger.info(f"Buying at: {buy_time.strftime('%H:%M')}")
            logger.info(f"Selling at: {sell_time.strftime('%H:%M')}")

            # Randomly choose fractional price to trade
            fractional = random.choice(self._fractionals)

            # UNCOMMENT FOR OPTIONS
            # Options trading part - likely uncomment
            # Put the second line within a list - was getting a bug and will see if it works
            option = (
                [self._options_list[option_idx % OPTN_LIST_LEN]]
                if 0 <= option_idx < OPTN_LIST_LEN
                else None
            )
            if option:
                logger.info(self._options_list[option_idx % OPTN_LIST_LEN])

            # Use Schedule module to schedule + execute buys at buy time
            # UNCOMMENT FOR OPTIONS: need to add options in the parameter here
            schedule.every().day.at(buy_time.strftime("%H:%M")).do(
                self._buy_across_brokers,
                sym_list=sym_list,
                options=option,                 # likely make this equal to option instead of empty list when doing options
                fractional=fractional,
            )

            # Use Schedule module to schedule + execute sells at sell time
            schedule.every().day.at(sell_time.strftime("%H:%M")).do(
                self._sell_across_brokers,
            )

            # Update the buy and sell time
            buy_time = sell_time + timedelta(minutes=self._time_between_groups)
            sell_time = buy_time + timedelta(minutes=self._time_between_buy_and_sell)

            # Update counts + indices
            current_idx = (current_idx + 4) % SYM_LIST_LEN
            count -= 4
            option_idx += 1

        logger.info("Done scheduling")

    def manual_override(
        self,
        orders: Union[list[StockOrder], list[OptionOrder]],
        action: ActionType = ActionType.SELL,
    ) -> None:
        """
        in the event the program crashes while selling and couldn't sell you can manually feed in the information and sell the stocks
        make sure to sell equities and options separately
        :param action:
        """
        if len(orders) == 0:
            logger.error("No stocks to sell")
            return

        if action == ActionType.CLOSE or action == ActionType.OPEN:
            option_brokers = self._choose_brokers(OPTN_BROKERS)
            self._perform_option_action(
                option_brokers,
                cast(list[OptionOrder], orders),
                action,
                main_program=False,
            )

        elif action == ActionType.SELL or action == ActionType.BUY:
            brokers = self._choose_brokers([])
            self._perform_action(
                brokers, cast(list[StockOrder], orders), action, main_program=False
            )

    def sell_leftover_positions(self) -> None:
        ''' 
        Sells any leftover positions
        '''
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

    def _perform_action(
        self,
        brokers: list[Broker],
        stock_list: list[StockOrder],
        action: ActionType,
        main_program: bool = True,
    ) -> None:
        '''
        Function that actually buys or sells the stock for each of the brokers
        '''

        for order in stock_list:
            
            for broker in brokers:
                try:
                    if action == ActionType.BUY:
                        broker.buy(order)
                        time.sleep(1)
                        # maybe add time.sleep(1) for robinhood error?
                    else:
                        broker.sell(order)
                        time.sleep(1)
                except Exception as e:
                    logger.error(e)
                    logger.error(
                        f"{broker.name()} Error {'buying' if action == ActionType.BUY else 'selling'} {order.quantity} '{order.sym}' stocks"
                    )

            # Set variables in the manager
            if main_program:
                if action == ActionType.BUY:
                    self._manager.set("COMPLETED", self._manager.get("COMPLETED") + 1)
                self._manager.set("PREVIOUS_STOCK_NAME", order.sym)

    def _perform_option_action(
        self,
        brokers: list[Broker],
        orders: list[OptionOrder],
        action: ActionType,
        main_program: bool = True,
    ) -> None:
        '''
        Executed buy or sell for options
        '''
        # print("DO WE GET HERE")
        for order in orders:

            for broker in brokers:
                try:
                    if action == ActionType.OPEN:
                        broker.buy_option(order)
                    else:
                        # hardcoding to fix error where it switches to PUT when selling
                        logger.info(f"BROKER: {broker.name()}")
                        logger.info(f"Prior to hardcoded change: {order}")
                        if order.option_type == OptionType.PUT:
                            order.option_type = OptionType.CALL
                        logger.info(f"After hardcoded change: {order}")
                        broker.sell_option(order)
                        logger.info("Finished selling option")
                except Exception as e:
                    logger.error(e)
                    logger.error(
                        f"{broker.name()} Error {'buying' if action == ActionType.OPEN else 'selling'} {order}"
                    )

            if main_program and action == ActionType.OPEN:
                self._manager.set(
                    "COMPLETED_OPTIONS",
                    self._manager.get("COMPLETED_OPTIONS") + 1,
                )

    def _buy_across_brokers(
        self,
        sym_list: list[str],
        options: list[OptionOrder],
        fractional: float,
    ) -> Any:
        '''
        Buys the specified equities, fractionals, and options across all brokers
        '''

        self._manager.set("STATUS", "Buy")

        # Orders list
        orders = [
            StockOrder(sym, *MarketData.get_stock_amount(sym)) for sym in sym_list
        ]

        # Fractional orders list
        frac_orders = [
            StockOrder(order.sym, fractional, order.price, order.order_type)
            for order in orders
            if order.price >= 20
        ]

        # Perform buys
        logger.info(options)
        logger.info("Currently Buying")
        self._perform_trade(EQUITY_BROKERS, orders, "STOCKS", ActionType.BUY)
        self._perform_trade(FRAC_BROKERS, frac_orders, "FRACTIONALS", ActionType.BUY,)

        # UNCOMMENT FOR OPTIONS
        if options:
            logger.info("About to buy options")
            self._perform_trade(OPTN_BROKERS, options, "OPTIONS", ActionType.OPEN)
            logger.info("Bought options")
        else:
            self._manager.set("OPTIONS", [])

        logger.info("Done Buying...\n")
        return schedule.CancelJob

    def _sell_across_brokers(self) -> Any:
        self._manager.set("STATUS", "Sell")

        orders = parse_stock_list(self._manager.get("STOCKS"))
        frac_orders = parse_stock_list(self._manager.get("FRACTIONALS"))

        logger.info("Currently Selling")
        self._perform_trade(EQUITY_BROKERS, orders, "STOCKS", ActionType.SELL)
        self._perform_trade(
            FRAC_BROKERS,
            frac_orders,
            "FRACTIONALS",
            ActionType.SELL,
        )

        # UNCOMMENT FOR OPTIONS
        option_order = parse_option_list(self._manager.get("OPTIONS"))
        
        if option_order:
            logger.info("About to sell options")
            logger.info(f"OPTIONS: {option_order}")
            self._perform_trade(OPTN_BROKERS, option_order, "OPTIONS", ActionType.CLOSE)
            logger.info("Bought options")

        logger.info("Done Selling...\n")
        return schedule.CancelJob

    def _perform_trade(
        self,
        brokers_str: list[str],
        orders: Union[list[StockOrder], list[OptionOrder]],
        key: str,
        action: ActionType,
    ) -> None:
        '''
        Performs the specified trades - could be buy or sell
        '''
        brokers = self._choose_brokers(brokers_str)
        # logger.info("In perform trade")
        # logger.info(orders)
        # logger.info(type(orders))

        # Logger stuff
        formatted_orders = format_list_of_orders(orders)

        # logger.info("after formatted orders")
        self._manager.set(key, formatted_orders)
        msg = (
            f"Buying {key}"
            if action == ActionType.BUY or action == ActionType.OPEN
            else f"Selling {key}"
        )
        logger.info(f"{msg}: {formatted_orders}")

        # Options trading execution
        if action == ActionType.OPEN or action == ActionType.CLOSE:
            # logger.info("REACHED")
            self._perform_option_action(
                brokers, cast(list[OptionOrder], orders), action
            )
            # logger.info("REACHED2")
        # Normal trade execution
        else:
            self._perform_action(brokers, cast(list[StockOrder], orders), action)

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
    buy_time = datetime.now() + timedelta(minutes=1)
    print(buy_time)

    pst_offset = timezone(timedelta(hours=-8))

    buy_time = datetime.now(pst_offset).replace(hour=6, minute=30, second=0, microsecond=0) + timedelta(minutes=1)
    print(buy_time)
    # pass
