import random
import time
from datetime import datetime, timedelta
from pyexpat import ExpatError
from typing import Any, Optional, Union

import schedule
from loguru import logger

from brokers import Robinhood, Fidelity, ETrade, TDAmeritrade, Schwab, Vanguard, IBKR
from utils.broker import Broker, OptionOrder, StockOrder
from utils.market_data import MarketData
from utils.program_manager import ProgramManager, SYM_LIST_LEN, SYM_LIST
from utils.report.post_processing import PostProcessing
from utils.report.report import ActionType, BrokerNames, OrderType
from utils.util import (
    format_list_of_orders,
    parse_option_string,
    parse_stock_string,
    process_option_input,
)


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
            TDAmeritrade(report_file, BrokerNames.TD, option_report_file),
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
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
                if len(schedule.get_jobs()) == 0:
                    logger.info("Finished trading")
                    break
        except:
            for broker in self._brokers:
                del broker

    def _pre_schedule_processing(self) -> tuple[int, int]:
        # program is run on new day
        if self._manager.get_program_data("DATE") != datetime.now().strftime("%x"):
            self._manager.update_program_data("DATE", datetime.now().strftime("%x"))
            # resuming from previous run
            if self._manager.get_program_data("COMPLETED") != SYM_LIST_LEN:
                last_stock_name = self._manager.get_program_data("PREVIOUS_STOCK_NAME")
                current_idx = (SYM_LIST.index(last_stock_name) + 1) % SYM_LIST_LEN
            else:  # choose random stock and begin from there
                random_sym = random.choice(SYM_LIST)
                current_idx = SYM_LIST.index(random_sym)
            self._manager.update_program_data("COMPLETED", 0)
            self._manager.update_program_data("COMPLETED_OPTIONS", 0)
        else:
            last_stock_name = self._manager.get_program_data("PREVIOUS_STOCK_NAME")
            current_idx = (SYM_LIST.index(last_stock_name) + 1) % SYM_LIST_LEN

        return current_idx, self._manager.get_program_data("COMPLETED_OPTIONS")

    def _schedule(self) -> None:
        current_idx, completed_options = self._pre_schedule_processing()

        # need to subtract in the case when re-running on same day and already completed some trades
        count = SYM_LIST_LEN - self._manager.get_program_data("COMPLETED")
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
                if 0 <= option_idx < OPTN_LIST_LEN * 2
                else None
            )
            if option:
                logger.info(self._options_list[option_idx % OPTN_LIST_LEN])

            schedule.every().day.at(buy_time.strftime("%H:%M")).do(
                self._buy_across_brokers,
                sym_list=sym_list,
                option=option,
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
        stock_list: Union[list[StockOrder], list[OptionOrder]],
        action: ActionType = ActionType.SELL,
    ) -> None:
        """
        in the event the program crashes while selling and couldn't sell you can manually feed in the information and sell the stocks
        :param stock_list: list of tuple (stock, amount)
        :param action:
        """
        if len(stock_list) == 0:
            logger.error("No stocks to sell")
            return

        if action == ActionType.CLOSE:
            option_brokers = self._choose_brokers(["TD", "RH", "E2", "FD", "SB", "VD"])
            for option in stock_list:
                if not isinstance(option, OptionOrder):
                    logger.error("Invalid option order")
                    return
                self._perform_option_action(
                    option_brokers, option, action, main_program=False
                )
        elif action == ActionType.SELL:
            brokers = self._choose_brokers([])
            stock_orders = [
                order for order in stock_list if isinstance(order, StockOrder)
            ]
            self._perform_action(brokers, stock_orders, action, main_program=False)

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
                    self._manager.update_program_data(
                        "COMPLETED", self._manager.get_program_data("COMPLETED") + 1
                    )
                self._manager.update_program_data("PREVIOUS_STOCK_NAME", order.sym)

    def _perform_option_action(
        self,
        brokers: list[Broker],
        order: OptionOrder,
        action: ActionType,
        main_program: bool = True,
    ) -> None:
        for broker in brokers:
            try:
                if action == ActionType.BUY:
                    broker.buy_option(order)
                else:
                    broker.sell_option(order)
            except Exception as e:
                logger.error(e)
                logger.error(
                    f"{broker.name()} Error {'buying' if action == ActionType.BUY else 'selling'} {order}"
                )

        if main_program and action == ActionType.BUY:
            self._manager.update_program_data(
                "COMPLETED_OPTIONS",
                self._manager.get_program_data("COMPLETED_OPTIONS") + 1,
            )

    def _buy_across_brokers(
        self,
        sym_list: list[str],
        option: OptionOrder,
        fractional: float,
    ) -> Any:
        self._manager.update_program_data("STATUS", "Buy")

        brokers = self._choose_brokers(["TD", "RH", "E2", "FD", "SB"])
        fractional_brokers = self._choose_brokers(["FD", "IF", "RH"])
        option_brokers = self._choose_brokers(["TD", "RH", "E2", "FD", "SB", "VD"])

        # order_list = [StockOrder(sym, quantity, price, OrderType, limit), ...]
        orders = [
            StockOrder(sym, *MarketData.get_stock_amount(sym), OrderType.MARKET)
            for sym in sym_list
        ]

        fractional_orders = [
            StockOrder(order.sym, fractional, order.price, order.order_type)
            for order in orders
            if order.price >= 20
        ]

        # big_orders = [
        #     StockOrder(order.sym, 100, order.price, order.order_type, order.limit_price)
        #     for order in orders
        #     if order.price <= 30
        # ]

        self._manager.update_program_data(
            "CURRENTLY_TRADING_STOCKS", format_list_of_orders(orders)
        )

        # self._manager.update_program_data("CURRENT_BIG_TRADES", big_trades)
        self._manager.update_program_data(
            "CURRENT_FRACTIONAL_TRADES", format_list_of_orders(fractional_orders)
        )

        logger.info(f"Currently Buying: {str(orders)}")
        self._perform_action(brokers, orders, ActionType.BUY)

        # logger.info(f"Big Trades: {str(big_trades)}")
        # self._perform_action(big_trades, ActionType.BUY, brokers = brokers, enable = ["FD"])
        #

        logger.info(f"Fractional Trades: {str(fractional_orders)}")
        self._perform_action(
            fractional_brokers,
            fractional_orders,
            ActionType.BUY,
        )

        if option:
            self._manager.update_program_data("CURRENTLY_TRADING_OPTION", str(option))
            logger.info(f"Currently Buying: {option}")
            self._perform_option_action(option_brokers, option, ActionType.BUY)
        else:
            self._manager.update_program_data("CURRENTLY_TRADING_OPTION", "")

        logger.info("Done Buying...\n")
        return schedule.CancelJob

    def _sell_across_brokers(
        self,
    ) -> Any:
        self._manager.update_program_data("STATUS", "Sell")

        brokers = self._choose_brokers(["TD", "RH", "E2", "FD", "SB"])
        fractional_brokers = self._choose_brokers(["FD", "IF", "RH"])
        option_brokers = self._choose_brokers(["TD", "RH", "E2", "FD", "SB", "VD"])

        orders = parse_stock_string(
            self._manager.get_program_data("CURRENTLY_TRADING_STOCKS")
        )

        # big_trades = self._manager.get_program_data("CURRENT_BIG_TRADES")
        fractional_trades = parse_stock_string(
            self._manager.get_program_data("CURRENT_FRACTIONAL_TRADES")
        )

        logger.info(f"Currently Selling: {format_list_of_orders(orders)}")
        self._perform_action(brokers, orders, ActionType.SELL)

        # logger.info(f"Big Trades: {str(big_trades)}")
        # self._perform_action(big_trades, ActionType.SELL, brokers = brokers, enable = ["FD"])

        logger.info(f"Fractional Trades: {format_list_of_orders(fractional_trades)}")
        self._perform_action(
            fractional_brokers,
            fractional_trades,
            ActionType.SELL,
        )

        option_order = parse_option_string(
            self._manager.get_program_data("CURRENTLY_TRADING_OPTION")
        )
        if option_order:
            logger.info(f"Currently Selling: {str(option_order)}")
            self._perform_option_action(option_brokers, option_order, ActionType.SELL)

        logger.info("Done Selling...\n")
        return schedule.CancelJob

    @staticmethod
    def generate_report(*, version: int = 0) -> None:
        processor = PostProcessing(version)
        # processor.optimized_generate_report(f"reports/original/report_xx_xx.csv")

    @staticmethod
    def generate_option_report(*, version: int = 0) -> None:
        processor = PostProcessing(version)
        # processor.generate_option_report(f"reports/original/option_report_xx_xx.csv")


if __name__ == "__main__":
    pass
