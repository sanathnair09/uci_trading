import time
from datetime import datetime, timedelta
import random
from pyexpat import ExpatError

import schedule
from loguru import logger

from utils.program_manager import ProgramManager, STOCK_LIST_LEN, SYM_LIST
from brokers import TDAmeritrade, Robinhood, ETrade, Schwab, Fidelity, IBKR
from utils.report.post_processing import PostProcessing
from utils.report.report import ActionType, BrokerNames


class AutomatedTrading:
    def __init__(self, *, time_between_buy_and_sell: float,
                 time_between_groups: float, enable_stdout = False):
        self._time_between_buy_and_sell = time_between_buy_and_sell
        self._time_between_groups = time_between_groups

        self._manager = ProgramManager(enable_stdout = enable_stdout)
        report_file = self._manager.report_file()

        self._brokers = [
            [TDAmeritrade(report_file, BrokerNames.TD), ],
            [Robinhood(report_file, BrokerNames.RH), ],
            [
                ETrade(report_file, BrokerNames.ET),
                # ETrade(report_file, BrokerNames.E2),
            ],
            [Fidelity(report_file, BrokerNames.FD)],
            [IBKR(report_file, BrokerNames.IF)],
            [Schwab(report_file, BrokerNames.SB)],
        ]

        self._fractionals = [.1, .25, .5, .75, 0.9]

        self._login_all()

    def _login_all(self):
        for group in self._brokers:
            for broker in group:
                broker.login()
        logger.info("Finished Logging into all brokers...")

    def _schedule(self):
        last_stock_name = self._manager.get_program_data("PREVIOUS_STOCK_NAME")
        current_idx = (SYM_LIST.index(last_stock_name) + 1) % STOCK_LIST_LEN

        buy_time = datetime.now() + timedelta(minutes = 1)
        sell_time = buy_time + timedelta(minutes = self._time_between_buy_and_sell)
        temp = 22  # 22 * 4 = 88 => get through 88 stocks ideally
        while temp > 0:
            sym_list = SYM_LIST[current_idx:current_idx + 4]  # chooses next 4 stocks to trade
            logger.info(f"Buying at: {buy_time.strftime('%H:%M')}")
            logger.info(f"Selling at: {sell_time.strftime('%H:%M')}")

            # randomly order brokers for each group
            # since we only trade one of each we don't need to shuffle inner list individually
            random.shuffle(self._brokers)

            # randomly choose fractional price to trade
            fractional = random.choice(self._fractionals)

            schedule.every().day.at(buy_time.strftime("%H:%M")).do(self._buy_across_brokers,
                                                                   sym_list = sym_list,
                                                                   fractional = fractional,
                                                                   brokers = self._brokers)
            schedule.every().day.at(sell_time.strftime("%H:%M")).do(self._sell_across_brokers,
                                                                    brokers = self._brokers)

            buy_time = sell_time + timedelta(minutes = self._time_between_groups)
            sell_time = buy_time + timedelta(minutes = self._time_between_buy_and_sell)
            current_idx = (current_idx + 5) % STOCK_LIST_LEN
            temp -= 1

        logger.info("Done scheduling")

    def start(self):
        self._schedule()

        while True:
            schedule.run_pending()
            time.sleep(1)
            if len(schedule.get_jobs()) == 0:
                logger.info("Finished trading")
                break

        # self.generate_report()

    def manual_override(self, stock_list):
        """
        in the event the program crashes while selling and couldn't sell you can manually feed in the information and sell the stocks
        :param stock_list: list of tuple (amount, stock)
        """
        stock_list = [(x[0], None, x[1]) for x in stock_list]  # needed to fix stock list for method
        self._perform_action(stock_list, ActionType.SELL, brokers = self._brokers)

    def sell_leftover_positions(self):
        for group in self._brokers:
            for broker in group:
                try:
                    leftover = broker.get_current_positions()
                    to_sell = [(int(amount), sym) for sym, amount in leftover if sym in SYM_LIST]
                    print(broker.name(), to_sell)
                    for amount, sym in to_sell:
                        broker.sell(sym, amount)
                        broker.save_report()
                except ExpatError:
                    print(broker.name(), "No positions")
                except Exception as e:
                    logger.error(e)

    def _perform_action(self, stock_list, action: ActionType, brokers: list, enable = None):
        if enable:
            selected = []
            for group in brokers:
                for br in group:
                    for item in enable:
                        if br.name() == item:
                            selected.append([br])
                            # since we are only trading one of each account we don't have to worry about dealing with multiple
            brokers = selected
        for amount, _, sym in stock_list:
            for group in brokers:
                for broker in group:
                    try:
                        if action == ActionType.BUY:
                            broker.buy(sym, amount)
                        else:
                            broker.sell(sym, amount)
                        broker.save_report()
                    except Exception as e:
                        logger.error(
                            f"{broker.name()} Error {'buying' if action == ActionType.BUY else 'selling'} {amount} '{sym}' stocks - ",
                            e)
            self._manager.update_program_data("PREVIOUS_STOCK_NAME", sym)

    def _buy_across_brokers(self, sym_list: list[str], fractional: float, brokers: list):
        self._manager.update_program_data("STATUS", "Buy")

        stock_list = [(*TDAmeritrade.get_stock_amount(sym), sym) for sym
                      in sym_list]
        big_trades = [(100, price, sym) for amount, price, sym in stock_list if price <= 30]
        fractional_trades = [(fractional, price, sym) for amount, price, sym in stock_list if
                             price >= 20]

        self._manager.update_program_data("CURRENTLY_TRADING_STOCKS", stock_list)
        self._manager.update_program_data("CURRENT_BIG_TRADES", big_trades)
        self._manager.update_program_data("CURRENT_FRACTIONAL_TRADES", fractional_trades)

        logger.info(f"Currently Buying: {str(stock_list)}")
        self._perform_action(stock_list, ActionType.BUY, brokers = brokers)

        logger.info(f"Big Trades: {str(big_trades)}")
        self._perform_action(big_trades, ActionType.BUY, brokers = brokers, enable = ["FD"])

        logger.info(f"Fractional Trades: {str(fractional_trades)}")
        self._perform_action(fractional_trades, ActionType.BUY, brokers = brokers,
                             enable = ["FD", "IF", "RH"])

        logger.info("Done Buying...\n")

    def _sell_across_brokers(self, brokers: list):
        self._manager.update_program_data("STATUS", "Sell")

        stock_list = self._manager.get_program_data("CURRENTLY_TRADING_STOCKS")
        big_trades = self._manager.get_program_data("CURRENT_BIG_TRADES")
        fractional_trades = self._manager.get_program_data("CURRENT_FRACTIONAL_TRADES")

        logger.info(f"Currently Selling: {str(stock_list)}")
        self._perform_action(stock_list, ActionType.SELL, brokers = brokers)

        logger.info(f"Big Trades: {str(big_trades)}")
        self._perform_action(big_trades, ActionType.SELL, brokers = brokers, enable = ["FD"])

        logger.info(f"Fractional Trades: {str(fractional_trades)}")
        self._perform_action(fractional_trades, ActionType.SELL, brokers = brokers,
                             enable = ["FD", "IF", "RH"])

        logger.info("Done Selling...\n")

    @staticmethod
    def generate_report(*, version = 0):
        # TODO: make sure to download fidelity data at end of each day
        processor = PostProcessing(version)
        date = datetime.now().strftime('%m_%d')
        # processor.optimized_generate_report(f"reports/original/report_{date}.csv")
        # processor.optimized_generate_report(f"reports/original/report_09_19.csv")
        # processor.optimized_generate_report(f"reports/original/report_09_20.csv")
        processor.optimized_generate_report(f"reports/original/report_09_21.csv")
        processor.optimized_generate_report(f"reports/original/report_09_25.csv")
        processor.optimized_generate_report(f"reports/original/report_09_26.csv")
        processor.optimized_generate_report(f"reports/original/report_09_27.csv")
        processor.optimized_generate_report(f"reports/original/report_09_28.csv")
        processor.optimized_generate_report(f"reports/original/report_09_29.csv")
