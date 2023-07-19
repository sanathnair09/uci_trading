import time
from datetime import datetime
from pathlib import Path

from selenium.webdriver import Keys
from selenium.webdriver.support.select import Select

from brokers import IBKR_LOGIN, IBKR_PASSWORD, TDAmeritrade
from utils.broker import Broker
from utils.debugger import BrokerError
from utils.misc import repeat
from utils.report import BrokerNames, OrderType, ActionType
from utils.selenium_helper import CustomChromeInstance
from selenium.webdriver.common.by import By
import re


class IBKR(Broker):
    """
    IBKR IS VERY SCARY
    """
    def __init__(self, report_file: Path, broker_name: BrokerNames):
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
        try:
            login_with_trading = self._chrome_inst.find(By.XPATH,
                                                        '/html/body/div[5]/div/div[2]/div/div/div[1]/button')
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
                         amount, None, None, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None)

    def sell(self, sym: str, amount: int):

        pre_stock_data = TDAmeritrade.get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_sell(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = TDAmeritrade.get_stock_data(sym)

        self._add_report(program_submitted, program_executed, None, sym, ActionType.SELL,
                         amount, None, None, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None)

    def _market_buy(self, sym: str, amount: int):
        sym_input = self._chrome_inst.waitForElementToLoad(By.ID, "cp-order-ticket-sl-input")
        self._chrome_inst.sendKeyboardInput(sym_input, sym)
        sym_input.send_keys(Keys.RETURN)
        time.sleep(2)
        sym_input.send_keys(Keys.RETURN)

        time.sleep(2)

        self._clear_quantity_input(amount)

        order_type_container = self._chrome_inst.find(By.ID, 'cp-ordertype-dropdown')
        order_type_container.click()

        self._chrome_inst.sendKeys(Keys.DOWN)
        self._chrome_inst.sendKeys(Keys.RETURN)

        time.sleep(1)

        # place_order = self._chrome_inst.find(By.ID, "cp-submit-order-Buy-btn")
        # place_order.click()

        preview_order = self._chrome_inst.find(By.ID, "cp-btn-preview")
        preview_order.click()

        time.sleep(2)
        input()

        last_row = self._chrome_inst.find(By.XPATH,
                                          '/html/body/div[5]/div/div[3]/div[1]/div/div[3]/table[1]/tr[5]')

        price = float(last_row.text[6:-4])

        if price <= self.THRESHOLD:
            place_order = self._chrome_inst.find(By.XPATH,
                                                 '/html/body/div[5]/div/div[5]/div/div/button[2]')
            place_order.click()
            '/html/body/div[5]/div/div[3]/div[1]/div/div[2]/div/button[2]'

            time.sleep(1)

            new_order = self._chrome_inst.find(By.XPATH,
                                               '/html/body/div[5]/div/div[3]/div[1]/div/div[2]/div/button[2]')
            new_order.click()
        else:
            back = self._chrome_inst.find(By.XPATH,
                                          '/html/body/div[5]/div/div[5]/div/div/button[1]')
            back.click()
            raise BrokerError(f"Couldn't buy since the price is over the threshold of {self.THRESHOLD}")

    def _market_sell(self, sym: str, amount: int):
        sym_input = self._chrome_inst.waitForElementToLoad(By.ID, "cp-order-ticket-sl-input")
        self._chrome_inst.sendKeyboardInput(sym_input, sym)
        sym_input.send_keys(Keys.RETURN)
        time.sleep(2)
        sym_input.send_keys(Keys.RETURN)
        time.sleep(1)

        sell_order = self._chrome_inst.waitForElementToLoad(By.XPATH,
                                                            '/html/body/div[5]/div/div[3]/div/div/div/div[2]/div[1]/div/div[2]/a[2]')
        sell_order.click()
        time.sleep(1)

        self._clear_quantity_input(amount)

        order_type_container = self._chrome_inst.find(By.ID, 'cp-ordertype-dropdown')
        order_type_container.click()

        self._chrome_inst.sendKeys(Keys.DOWN)
        self._chrome_inst.sendKeys(Keys.RETURN)

        time.sleep(1)

        place_order = self._chrome_inst.find(By.ID, "cp-submit-order-Sell-btn")
        place_order.click()

        time.sleep(2)

        new_order = self._chrome_inst.find(By.XPATH,
                                           '/html/body/div[5]/div/div[3]/div[1]/div/div[2]/div/button[2]')
        new_order.click()

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _clear_quantity_input(self, amount):
        amount_elem_loaded = self._chrome_inst.waitForTextInValue(By.ID, "cp-qty-input", "100")
        if amount_elem_loaded:
            amount_elem = self._chrome_inst.find(By.ID, 'cp-qty-input')
            # to remove the default 100 that is in the shares field
            amount_elem.clear()
            amount_elem.send_keys(Keys.BACKSPACE)
            amount_elem.send_keys(Keys.BACKSPACE)
            amount_elem.send_keys(Keys.BACKSPACE)
            self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

        time.sleep(1)

    def get_current_positions(self):
        pass


if __name__ == '__main__':
    a = IBKR("temp.csv")
    a.login()
    a.buy("VRM", 1)
    time.sleep(1)
    a.sell("VRM", 1)
