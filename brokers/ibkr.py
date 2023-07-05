import time
from datetime import datetime

from selenium.webdriver import Keys
from selenium.webdriver.support.select import Select

from brokers import IBKR_LOGIN, IBKR_PASSWORD, TDAmeritrade
from utils.broker import Broker
from utils.misc import repeat
from utils.report import BrokerNames, OrderType, ActionType
from utils.selenium_helper import CustomChromeInstance
from selenium.webdriver.common.by import By


class IBKR(Broker):
    def __init__(self, report_file):
        super().__init__(report_file)
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

        self._add_report( program_submitted, program_executed, None, sym, ActionType.BUY,
                         amount, None, None, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None, BrokerNames.IF)

    def sell(self, sym: str, amount: int):
        
        pre_stock_data = TDAmeritrade.get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_sell(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = TDAmeritrade.get_stock_data(sym)

        self._add_report( program_submitted, program_executed, None, sym, ActionType.SELL,
                         amount, None, None, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None, BrokerNames.IF)

    def _market_buy(self, sym: str, amount: int):
        sym_input = self._chrome_inst.waitForElementToLoad(By.ID, "cp-order-ticket-sl-input")
        self._chrome_inst.sendKeyboardInput(sym_input, sym)
        sym_input.send_keys(Keys.RETURN)
        time.sleep(2)
        sym_input.send_keys(Keys.RETURN)

        time.sleep(2)

        amount_elem = self._chrome_inst.find(By.ID, "cp-qty-input")
        amount_elem.send_keys(Keys.BACKSPACE)
        amount_elem.send_keys(Keys.BACKSPACE)
        amount_elem.send_keys(
            Keys.BACKSPACE)  # to remove the default 100 that is in the shares field
        self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

        order_type_container = self._chrome_inst.find(By.ID, 'cp-ordertype-dropdown')
        order_type_container.click()

        self._chrome_inst.sendKeys(Keys.DOWN)
        self._chrome_inst.sendKeys(Keys.RETURN)

        time.sleep(1)

        place_order = self._chrome_inst.find(By.ID, "cp-submit-order-Buy-btn")
        place_order.click()

        time.sleep(2)

        new_order = self._chrome_inst.find(By.XPATH,
                                           '/html/body/div[5]/div/div[3]/div[1]/div/div[2]/div/button[2]')
        new_order.click()

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

        amount_elem = self._chrome_inst.find(By.ID, "cp-qty-input")
        amount_elem.send_keys(Keys.BACKSPACE)
        amount_elem.send_keys(Keys.BACKSPACE)
        amount_elem.send_keys(
            Keys.BACKSPACE)  # to remove the default 100 that is in the shares field
        self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

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


if __name__ == '__main__':
    a = IBKR("temp.csv")
    a.login()
    a.buy("VRM", 1)
    time.sleep(2)
    a.buy("VRM", 1)
    time.sleep(5)
    a.sell("VRM", 2)
    input()
