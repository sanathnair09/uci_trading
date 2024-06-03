import random
import time
from datetime import datetime, timedelta
from pyexpat import ExpatError
from typing import Any, Optional, Union, cast

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


EQUITY_BROKERS = ["TD", "RH", "E2", "FD", "SB"]
FRAC_BROKERS = ["FD", "IF", "RH"]
OPTN_BROKERS = ["TD", "RH", "E2", "FD", "SB", "VD"]


class AutomatedTrading:
    def __init__(
        self,
        *,
        time_between_buy_and_sell: float,
        time_between_groups: float,
        enable_stdout: bool = False,
    ):
        logger.info("Beginning Automated Trading")

        self._options_list = process_option_input()
        logger.info("Trading Options: " + str(self._options_list))

        self._time_between_buy_and_sell = time_between_buy_and_sell
        self._time_between_groups = time_between_groups

        self._manager = ProgramManager(enable_stdout=enable_stdout)
        report_file, option_report_file = (
            self._manager.report_file,
            self._manager.option_report_file,
        )

        self._brokers: list[Broker] = [
            Robinhood(report_file, BrokerNames.RH, option_report_file),
            ETrade(report_file, BrokerNames.E2, option_report_file),
            Fidelity(report_file, BrokerNames.FD, option_report_file),
            # IBKR(report_file, BrokerNames.IF),
            Schwab(report_file, BrokerNames.SB, option_report_file),
            Vanguard(report_file, BrokerNames.VD, option_report_file),
        ]

        self._fractionals = [0.1, 0.25, 0.5, 0.75, 0.9]

        self._login_all()

    def _login_all(self) -> None:
        for broker in self._brokers:
            broker.login()
        logger.info("Finished Logging into all brokers...")

    def start(self) -> None:
        self._schedule()
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

    def _schedule(self) -> None:
        current_idx, completed_options = self._pre_schedule_processing()

        # need to subtract in the case when re-running on same day and already completed some trades
        count = SYM_LIST_LEN - self._manager.get("COMPLETED")
        option_idx = completed_options  # needed for array indexing
        OPTN_LIST_LEN = len(self._options_list)
        SELL_TIME_LIMIT = datetime.now().replace(
            hour=12, minute=30, second=0, microsecond=0
        )

        buy_time = datetime.now() + timedelta(minutes=1)
        sell_time = buy_time + timedelta(minutes=self._time_between_buy_and_sell)

        while count > 0 and sell_time < SELL_TIME_LIMIT:
            # chooses next 4 stocks to trade
            sym_list = SYM_LIST[current_idx : current_idx + 4]
            # sym_list = [sym for sym in sym_list if MarketData.validate_stock(sym)]

            logger.info(sym_list)
            logger.info(f"Buying at: {buy_time.strftime('%H:%M')}")
            logger.info(f"Selling at: {sell_time.strftime('%H:%M')}")

            # randomly choose fractional price to trade
            fractional = random.choice(self._fractionals)

            option = (
                self._options_list[option_idx % OPTN_LIST_LEN]
                if 0 <= option_idx < OPTN_LIST_LEN
                else None
            )
            if option:
                logger.info(self._options_list[option_idx % OPTN_LIST_LEN])

            schedule.every().day.at(buy_time.strftime("%H:%M")).do(
                self._buy_across_brokers,
                sym_list=sym_list,
                options=[option],
                fractional=fractional,
            )

            schedule.every().day.at(sell_time.strftime("%H:%M")).do(
                self._sell_across_brokers,
            )

            buy_time = sell_time + timedelta(minutes=self._time_between_groups)
            sell_time = buy_time + timedelta(minutes=self._time_between_buy_and_sell)
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
        for order in stock_list:
            for broker in brokers:
                try:
                    if action == ActionType.BUY:
                        broker.buy(order)
                    else:
                        broker.sell(order)
                except Exception as e:
                    logger.error(e)
                    logger.error(
                        f"{broker.name()} Error {'buying' if action == ActionType.BUY else 'selling'} {order.quantity} '{order.sym}' stocks"
                    )

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
        for order in orders:
            for broker in brokers:
                try:
                    if action == ActionType.OPEN:
                        broker.buy_option(order)
                    else:
                        broker.sell_option(order)
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
        self._manager.set("STATUS", "Buy")
        orders = [
            StockOrder(sym, *MarketData.get_stock_amount(sym)) for sym in sym_list
        ]

        frac_orders = [
            StockOrder(order.sym, fractional, order.price, order.order_type)
            for order in orders
            if order.price >= 20
        ]
        logger.info("Currently Buying")
        self._perform_trade(EQUITY_BROKERS, orders, "STOCKS", ActionType.BUY)
        self._perform_trade(
            FRAC_BROKERS,
            frac_orders,
            "FRACTIONALS",
            ActionType.BUY,
        )

        if options:
            self._perform_trade(OPTN_BROKERS, options, "OPTIONS", ActionType.OPEN)
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
        option_order = parse_option_list(self._manager.get("OPTIONS"))
        if option_order:
            self._perform_trade(OPTN_BROKERS, option_order, "OPTIONS", ActionType.CLOSE)

        logger.info("Done Selling...\n")
        return schedule.CancelJob

    def _perform_trade(
        self,
        brokers_str: list[str],
        orders: Union[list[StockOrder], list[OptionOrder]],
        key: str,
        action: ActionType,
    ) -> None:
        brokers = self._choose_brokers(brokers_str)

        formatted_orders = format_list_of_orders(orders)
        self._manager.set(key, formatted_orders)
        msg = (
            f"Buying {key}"
            if action == ActionType.BUY or action == ActionType.OPEN
            else f"Selling {key}"
        )
        logger.info(f"{msg}: {formatted_orders}")
        if action == ActionType.OPEN or action == ActionType.CLOSE:
            self._perform_option_action(
                brokers, cast(list[OptionOrder], orders), action
            )
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
    pass
