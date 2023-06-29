import time
from datetime import datetime

from selenium.webdriver import Keys

from brokers import FIDELITY_LOGIN, FIDELITY_PASSWORD, TDAmeritrade
from utils.broker import Broker
from utils.report import BrokerNames, OrderType, ActionType
from utils.selenium_helper import CustomChromeInstance
from selenium.webdriver.common.by import By


#
class Fidelity(Broker):
    def __init__(self, report_file):
        super().__init__(report_file)
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open("https://digital.fidelity.com/prgw/digital/login/full-page")

    def login(self):
        login_input_elem = self._chrome_inst.find(By.XPATH, '//*[@id="userId-input"]')
        self._chrome_inst.sendKeyboardInput(login_input_elem, FIDELITY_LOGIN)
        password_input_elem = self._chrome_inst.find(By.ID, "password")
        self._chrome_inst.sendKeyboardInput(password_input_elem, FIDELITY_PASSWORD)
        self._chrome_inst.waitToClick("fs-login-button")
        time.sleep(5)  # will have to play with time depending on your internet speeds
        self._chrome_inst.open(
            "https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry")

    def _get_stock_data(self, sym: str):
        pass

    def buy(self, sym: str, amount: int):
        date = datetime.now().strftime('%x')
        pre_stock_data = TDAmeritrade.get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_buy(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = TDAmeritrade.get_stock_data(sym)


        self._add_report(date, program_submitted, program_executed, None, sym, ActionType.BUY,
                         amount, None, None, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None, BrokerNames.FD)

    def sell(self, sym: str, amount: int):
        date = datetime.now().strftime('%x')
        pre_stock_data = TDAmeritrade.get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_sell(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = TDAmeritrade.get_stock_data(sym)

        self._add_report(date, program_submitted, program_executed, None, sym, ActionType.SELL,
                         amount, None, None, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None, BrokerNames.FD)

    # def _get_order_num(self):
    #     return self._chrome_inst.find(By.XPATH, '/html/body/div[3]/ap122489-ett-component/div/order-entry-base/div/div/div[2]/equity-order-routing/order-confirm/div/div/order-received/div/div/div/div[3]').text

    def _place_new_order(self):
        place_new_order_btn = self._chrome_inst.waitForElementToLoad(By.ID, "eq-ticket__enter-new-order")
        place_new_order_btn.click()

    def _market_buy(self, sym: str, amount: int):
        symbol_elem = self._chrome_inst.waitForElementToLoad(By.ID, "eq-ticket-dest-symbol")
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)

        time.sleep(2)

        buy_elem = self._chrome_inst.find(By.ID, "action-buy")
        buy_elem.click()

        amount_elem = self._chrome_inst.find(By.XPATH, '//*[@id="eqt-shared-quantity"]')
        self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

        market_elem = self._chrome_inst.find(By.ID, "market-yes")
        market_elem.click()

        preview_btn = self._chrome_inst.find(By.ID, "previewOrderBtn")
        preview_btn.click()

        time.sleep(3)

        place_order_btn = self._chrome_inst.find(By.ID, "placeOrderBtn")
        place_order_btn.click()

        # order_num = self._get_order_num()

        self._place_new_order()
        # return order_num



    def _market_sell(self, sym: str, amount: int):
        symbol_elem = self._chrome_inst.waitForElementToLoad(By.ID, "eq-ticket-dest-symbol")
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)

        time.sleep(2)

        sell_elem = self._chrome_inst.find(By.ID, "action-sell")
        sell_elem.click()

        amount_elem = self._chrome_inst.find(By.XPATH, '//*[@id="eqt-shared-quantity"]')
        self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

        market_elem = self._chrome_inst.find(By.ID, "market-yes")
        market_elem.click()

        preview_btn = self._chrome_inst.find(By.ID, "previewOrderBtn")
        preview_btn.click()

        time.sleep(3)

        place_order_btn = self._chrome_inst.waitForElementToLoad(By.ID, "placeOrderBtn")
        place_order_btn.click()

        # order_num = self._get_order_num()

        self._place_new_order()
        # return order_num

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    


if __name__ == '__main__':
    a = Fidelity("temp.csv")
    a.login()
    a.buy("W", 2)
    a.save_report()
