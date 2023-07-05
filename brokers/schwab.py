import time
from datetime import datetime
from pathlib import Path
from typing import Union

from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from utils.broker import Broker
from brokers import SCHWAB_LOGIN, SCHWAB_PASSWORD, TDAmeritrade
from utils.selenium_helper import CustomChromeInstance
from utils.report import OrderType, ActionType, BrokerNames


class Schwab(Broker):
    def __init__(self, report_file: Union[Path, str]) -> None:
        super().__init__(report_file)
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open("https://client.schwab.com/Login/SignOn/CustomerCenterLogin.aspx")
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
                         False, None, None, BrokerNames.SB)

    def sell(self, sym: str, amount: int):
        pre_stock_data = TDAmeritrade.get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_sell(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = TDAmeritrade.get_stock_data(sym)

        self._add_report( program_submitted, program_executed, None, sym, ActionType.SELL,
                         amount, None, None, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None, BrokerNames.SB)

    def _market_buy(self, sym: str, amount: int):

        symbol_elem = self._chrome_inst.waitForElementToLoad(By.XPATH, '//*[@id="_txtSymbol"]')
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)
        time.sleep(2)
        action_dropdown = Select(
            self._chrome_inst.waitForElementToLoad(By.XPATH, '//*[@id="_action"]'))
        action_dropdown.select_by_visible_text("Buy")
        # order_type_dropdown = Select(self._chrome_inst.find(By.XPATH, '//*[@id="order-type"]'))
        # order_type_dropdown.select_by_visible_text("Market")

        amount_elem = self._chrome_inst.find(By.XPATH, '//*[@id="_txtQty"]')
        self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

        self._chrome_inst.scroll(500)
        time.sleep(1)
        review_order_btn = self._chrome_inst.find(By.XPATH,
                                                  '//*[@id="mcaio-footer"]/div/div[2]/button[2]')
        review_order_btn.click()
        self._chrome_inst.scroll(350)
        time.sleep(1) # wait for page to load
        place_order_btn = self._chrome_inst.waitForElementToLoad(By.XPATH,
                                                                 '//*[@id="mtt-place-button"]')
        place_order_btn.click()

        self._chrome_inst.open("https://client.schwab.com/app/trade/tom/#/trade")
        time.sleep(2) # wait for trade page to load again


    def _market_sell(self, sym: str, amount: int):
        symbol_elem = self._chrome_inst.waitForElementToLoad(By.XPATH, '//*[@id="_txtSymbol"]')
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)
        time.sleep(2)
        self._chrome_inst.find(By.XPATH, '//*[@id="mcaio-sellAllHandle"]').click()

        amount_elem = self._chrome_inst.find(By.XPATH,
                                             '//*[@id="_txtQty"]')  # techincally uncessary since sell all will sell whatever was bought in the previous
        self._chrome_inst.sendKeyboardInput(amount_elem,
                                            str(amount))  # however in the event that there were extras or something this only sells the ones we want

        # order_type_dropdown = Select(self._chrome_inst.find(By.XPATH, '//*[@id="order-type"]'))
        # order_type_dropdown.select_by_visible_text("Market")
        self._chrome_inst.scroll(500) # FIXME: scroll so button in view
        time.sleep(1)
        review_order_btn = self._chrome_inst.find(By.XPATH,
                                                  '//*[@id="mcaio-footer"]/div/div[2]/button[2]')

        review_order_btn.click()
        self._chrome_inst.scroll(350)
        time.sleep(1)
        place_order_btn = self._chrome_inst.waitForElementToLoad(By.XPATH,
                                                                 '//*[@id="mtt-place-button"]')
        place_order_btn.click()

        self._chrome_inst.open("https://client.schwab.com/app/trade/tom/#/trade")
        time.sleep(2) # wait for trade page to load again

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def login(self):
        # frame = self._chrome_inst.find(By.ID, "iframeWrapper")
        self._chrome_inst.switchToFrame("lmsSecondaryLogin")
        login_input_elem = self._chrome_inst.find(By.ID, "loginIdInput")
        self._chrome_inst.sendKeyboardInput(login_input_elem, SCHWAB_LOGIN)
        password_input_elem = self._chrome_inst.find(By.ID, "passwordInput")
        self._chrome_inst.sendKeyboardInput(password_input_elem, SCHWAB_PASSWORD)
        temp = self._chrome_inst.waitForElementToLoad(By.XPATH,
                                                      '/html/body/div/lms-app-root/section/div/div/section/lms-login-one-step-container/lms-login-one-step/section/div[1]/div[6]/div/select')
        select_elem = Select(temp)
        select_elem.select_by_visible_text("Trade Ticket")
        self._chrome_inst.waitToClick("btnLogin")
        time.sleep(2)  # TODO: use selenium wait

    


if __name__ == '__main__':
    s = Schwab("temp.csv")
    s.login()
    s.buy("W", 1)
    time.sleep(3)
    s.sell("W", 1)
    s.save_report()
