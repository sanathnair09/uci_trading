import time
from datetime import datetime

from selenium.webdriver import Keys

from brokers import IBKR_LOGIN, IBKR_PASSWORD
from utils.broker import Broker
from utils.misc import repeat
from utils.report import  BrokerNames, OrderType, ActionType
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

        time.sleep(3) # wait for the trade window to appear on screen

        self.fix_permission()

    @repeat()
    def fix_permission(self):
        try:
            login_with_trading = self._chrome_inst.find(By.XPATH, '/html/body/div[5]/div/div[2]/div/div/div[1]/button')
            login_with_trading.click()
        except:
            pass

    def _get_stock_data(self, sym: str):
        pass

    def buy(self, sym: str, amount: int):
        pass

    def sell(self, sym: str, amount: int):
        pass

    def _market_buy(self, sym: str, amount: int):
        sym_input = self._chrome_inst.waitForElementToLoad(By.ID, "cp-order-ticket-sl-input")
        self._chrome_inst.sendKeyboardInput(sym_input, sym)
        sym_input.send_keys(Keys.RETURN)
        time.sleep(2)
        sym_input.send_keys(Keys.RETURN)

        time.sleep(3)

        amount_elem = self._chrome_inst.find(By.ID, "cp-qty-input")
        amount_elem.send_keys(Keys.BACKSPACE)
        amount_elem.send_keys(Keys.BACKSPACE)
        amount_elem.send_keys(Keys.BACKSPACE) # to remove the default 100 that is in the shares field
        self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

        order_type_dropdown = self._chrome_inst.find(By.ID, 'cp-ordertype-dropdown')
        order_type_dropdown.click()
        input()
        self._chrome_inst.find(By.XPATH, '/html/body/div[5]/div/div[3]/div/div/div/div[2]/div[2]/div[3]/span[1]/span/ul/li[2]').click()

        place_order = self._chrome_inst.find(By.ID, "cp-submit-order-Buy-btn")
        place_order.click()

        new_order = self._chrome_inst.find(By.XPATH, '/html/body/div[6]/div/div[3]/div[1]/div/div[2]/div/button[2]')
        new_order.click()



    def _market_sell(self, sym: str, amount: int):
        pass

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError


if __name__ == '__main__':
    a = IBKR("temp.csv")
    a.login()
    a._market_buy("VRM", 1)
    input()
