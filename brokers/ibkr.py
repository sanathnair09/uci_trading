import time
from datetime import datetime
from io import StringIO

import pandas as pd
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys

from brokers import IBKR_LOGIN, IBKR_PASSWORD, TDAmeritrade
from utils.broker import Broker
from utils.misc import repeat
from utils.report.report import BrokerNames, OrderType, ActionType
from utils.selenium_helper import CustomChromeInstance
from selenium.webdriver.common.by import By


class IBKR(Broker):
    """
    IBKR IS VERY SCARY
    """

    def __init__(self, report_file, broker_name: BrokerNames):
        super().__init__(report_file, broker_name)
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open("https://ndcdyn.interactivebrokers.com/sso/Login")

    def login(self):
        username_elem = self._chrome_inst.find(By.XPATH,
                                               "/html/body/section[1]/div/div/div[2]/div[2]/form[2]/div[1]/fieldset[1]/div/input")
        self._chrome_inst.sendKeyboardInput(username_elem, IBKR_LOGIN)

        password_elem = self._chrome_inst.find(By.XPATH,
                                               "/html/body/section[1]/div/div/div[2]/div[2]/form[2]/div[1]/fieldset[2]/div/input")
        self._chrome_inst.sendKeyboardInput(password_elem, IBKR_PASSWORD)

        login_btn = self._chrome_inst.find(By.XPATH,
                                           "/html/body/section[1]/div/div/div[2]/div[2]/form[2]/div[2]/div[1]/button")
        login_btn.click()

        print("Waiting for 2fa...", end = "")
        input()

        trade_nav = self._chrome_inst.find(By.XPATH,
                                           "/html/body/div[1]/header/section/div/div/div[3]/div[3]/div/button")
        trade_nav.click()

        time.sleep(2)  # wait for the trade window to appear on screen

        self.fix_permission()

    @repeat()
    def fix_permission(self):
        # TODO
        try:
            login_with_trading = self._chrome_inst.find(By.XPATH,
                                                        '/html/body/div[4]/div/div[2]/div/div/div[1]/button')
            login_with_trading.click()
        except:
            pass

    def _get_stock_data(self, sym: str):
        pass

    def buy(self, sym: str, amount: int):
        pre_stock_data = TDAmeritrade.get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_buy(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = TDAmeritrade.get_stock_data(sym)

        self._add_report(program_submitted, program_executed, None, sym, ActionType.BUY,
                         amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None)

    def sell(self, sym: str, amount: int):
        pre_stock_data = TDAmeritrade.get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_sell(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = TDAmeritrade.get_stock_data(sym)

        self._add_report(program_submitted, program_executed, None, sym, ActionType.SELL,
                         amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None)

    def _market_buy(self, sym: str, amount: int):
        try:
            self._choose_stock(sym)
            self._set_amount(amount)
            self._choose_order_type(OrderType.MARKET, ActionType.BUY)
            self._validate_order(sym, ActionType.BUY)
        except Exception as e:
            self._error_count += 1
            raise e

    def _market_sell(self, sym: str, amount: int):
        try:
            self._choose_stock(sym)
            self._set_sell()
            self._set_amount(amount)
            self._choose_order_type(OrderType.MARKET, ActionType.SELL)
            self._validate_order(sym, ActionType.SELL)
        except Exception as e:
            self._error_count += 1
            raise e

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _test_variation(self, path, *args):
        """
        place the numbers in args in probability of expecting it (i.e if 5 is more likely than 4 do 5, 4)
        :param path:
        :param args:
        :return:
        """
        for arg in args:
            test_path = path.replace("{f}", str(arg))
            try:
                res = self._chrome_inst.waitForElementToLoad(By.XPATH, test_path, 5)
                return res
            except:
                pass
        raise NoSuchElementException()

    def _choose_stock(self, sym: str):
        sym_input = self._test_variation(
            '/html/body/div[{f}]/div/div[2]/div[1]/div[1]/div/div/form/div/span/span/input', 5, 6,
            7, 4)
        self._chrome_inst.sendKeyboardInput(sym_input, sym)
        sym_input.send_keys(Keys.RETURN)
        time.sleep(1)

        try:
            select_stock = self._test_variation(
                '/html/body/div[{f}]/div/div[2]/div[1]/div[1]/div/div/form/div/div[1]/ul[1]/li/ul/li[1]/div/a',
                5, 6, 7, 4)
            select_stock.click()
            time.sleep(1)
        except NoSuchElementException as _:
            pass  # some stocks don't have other choices like options etc

        time.sleep(1)

    def _set_sell(self):
        sell_tab = self._chrome_inst.find(By.XPATH, '//*[@id="sellTab"]')
        sell_tab.click()
        time.sleep(1)

    def _set_amount(self, amount):
        quantity_elem = self._test_variation(
            '/html/body/div[{f}]/div/div[3]/div[2]/div/div[2]/div[1]/form/div[3]/div/div[1]/div/div[1]/span/span/input',
            5, 6, 7, 4)
        if quantity_elem:
            # to remove the default 100 that is in the shares field
            quantity_elem.clear()
            quantity_elem.send_keys(Keys.BACKSPACE)
            quantity_elem.send_keys(Keys.BACKSPACE)
            quantity_elem.send_keys(Keys.BACKSPACE)
            self._chrome_inst.sendKeyboardInput(quantity_elem, str(amount))

        time.sleep(1)

    def _choose_order_type(self, order_type: OrderType, action_type: ActionType):
        if action_type == ActionType.BUY:
            dropdown = self._test_variation(
                '/html/body/div[{f}]/div/div[3]/div[2]/div/div[2]/div[1]/form/div[3]/div/div[3]/div[1]/span/span',
                5, 6, 7, 4)
        else:
            dropdown = self._chrome_inst.find(By.XPATH,
                                              '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[1]/form/div[3]/div/div[2]/div[1]/span')
        dropdown.click()
        if order_type == OrderType.MARKET:
            self._chrome_inst.sendKeys(Keys.DOWN)
            self._chrome_inst.sendKeys(Keys.DOWN)
            self._chrome_inst.sendKeys(Keys.RETURN)
        # limit is default

    def _go_back(self, action_type: ActionType):
        if action_type == ActionType.BUY:
            back_btn = self._chrome_inst.find(By.XPATH,
                                              '//*[@id="orderTicketBuyTabPanel"]/div/div[2]/div[2]/div[2]/div/button[1]')
            back_btn.click()
        else:
            back_btn = self._chrome_inst.find(By.XPATH,
                                              '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[2]/div[2]/div/button[1]')
            back_btn.click()

    def _validate_order(self, sym: str, action_type: ActionType):
        preview_btn = self._chrome_inst.find(By.XPATH, '//*[@id="cp-btn-preview"]')
        preview_btn.click()
        time.sleep(1)

        try:
            if action_type == ActionType.BUY:
                total_text = self._chrome_inst.find(By.XPATH,
                                                    '//*[@id="orderTicketBuyTabPanel"]/div/div[2]/div[1]/div/div[1]/div/table/tr[5]/td[2]').text
                price = float(total_text[:-4].replace(",", ""))
                logger.info(f"IB - {sym} = {total_text}")

                if price <= self.THRESHOLD:
                    place_order = self._chrome_inst.find(By.XPATH,
                                                         '//*[@id="orderTicketBuyTabPanel"]/div/div[2]/div[2]/div[2]/div/button[2]')
                    place_order.click()
                    time.sleep(1)
                    new_order = self._chrome_inst.find(By.XPATH,
                                                       '//*[@id="orderTicketBuyTabPanel"]/div/div[2]/div[1]/div/div[4]/button[2]')
                    new_order.click()
                else:
                    self._go_back(action_type)

                    logger.error(f"Buying more than threshold")
            else:  # SELL
                post_trade_positions = self._chrome_inst.find(By.XPATH,
                                                              '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[1]/div/div[2]/div/table/tr[2]/td[4]')
                position_text = post_trade_positions.text
                if '-' in position_text:
                    self._go_back(action_type)

                    logger.error(
                        f"Selling more than what is owned. Post-trade position: {position_text}")
                else:
                    place_order = self._chrome_inst.find(By.XPATH,
                                                         '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[2]/div[2]/div/button[2]')
                    place_order.click()
                    time.sleep(2)
                    new_order = self._chrome_inst.find(By.XPATH,
                                                       '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[1]/div/div[4]/button[2]')
                    new_order.click()
        except Exception as e:
            logger.error(f"Error completing IF action for {sym}")

    def resolve_errors(self):
        if self._error_count > 0:
            self._chrome_inst.refresh()
            self._error_count = 0

    def get_current_positions(self) -> list[tuple[str, float]]:
        self._chrome_inst.open(
            "https://portal.interactivebrokers.com/portal/?action=ACCT_MGMT_MAIN&loginType=1&clt=0#/portfolio")
        time.sleep(5)
        positions = []
        try:
            page_source = self._chrome_inst.get_page_source()
            df = pd.read_html(StringIO(page_source))
            df = df[0]
            positions = df[["Instrument", "Position"]].to_numpy()
            positions = [(sym if '●' not in sym else sym[1:], float(amount)) for sym, amount in
                         positions]
        except Exception as e:
            print(e)
        return positions


if __name__ == '__main__':
    a = IBKR("temp.csv", BrokerNames.IF)
    a.login()
    a.get_current_positions()
    pass
