import time
from datetime import datetime

from selenium.common import NoSuchElementException
from selenium.webdriver import Keys

from brokers import FIDELITY_LOGIN, FIDELITY_PASSWORD, TDAmeritrade
from utils.broker import Broker
from utils.report import BrokerNames, OrderType, ActionType, StockData
from utils.selenium_helper import CustomChromeInstance
from selenium.webdriver.common.by import By


#
class Fidelity(Broker):
    def __init__(self, report_file, broker_name: BrokerNames):
        super().__init__(report_file, broker_name)
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
        time.sleep(1)

    def _get_stock_data(self, sym: str):
        symbol_elem = self._chrome_inst.waitForElementToLoad(By.ID, "eq-ticket-dest-symbol")
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)

        time.sleep(1)

        bid_price = self._chrome_inst.find(By.XPATH,
                                           '//*[@id="quote-panel"]/div/div[2]/div[1]/div/span/span').text

        ask_price = self._chrome_inst.find(By.XPATH,
                                           '//*[@id="quote-panel"]/div/div[2]/div[2]/div/span/span').text

        volume = self._chrome_inst.find(By.XPATH,
                                        '//*[@id="quote-panel"]/div/div[2]/div[3]/div/span').text.replace(
            ",", "")
        try:
            quote = self._chrome_inst.find(By.XPATH,
                                           '//*[@id="ett-more-quote-info"]/div/div/div/div/div[2]/div[1]/div[2]/span').text
        except NoSuchElementException:
            self._chrome_inst.find(By.ID, 'ett-more-less-quote-link').click()
            time.sleep(0.5)
            quote = self._chrome_inst.find(By.XPATH,
                                           '//*[@id="ett-more-quote-info"]/div/div/div/div/div[2]/div[1]/div[2]/span').text

        return StockData(float(ask_price), float(bid_price), float(quote[1:]), float(volume))

    def buy(self, sym: str, amount: int):
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_buy(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(sym)

        self._add_report(program_submitted, program_executed, None, sym, ActionType.BUY,
                         amount, None, None, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None)

    def sell(self, sym: str, amount: int):
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_sell(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(sym)

        self._add_report(program_submitted, program_executed, None, sym, ActionType.SELL,
                         amount, None, None, pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None)

    # def _get_order_num(self):
    #     return self._chrome_inst.find(By.XPATH, '/html/body/div[3]/ap122489-ett-component/div/order-entry-base/div/div/div[2]/equity-order-routing/order-confirm/div/div/order-received/div/div/div/div[3]').text

    def _place_new_order(self):
        place_new_order_btn = self._chrome_inst.waitForElementToLoad(By.ID,
                                                                     "eq-ticket__enter-new-order")
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
        # amount_elem.send_keys(Keys.RETURN)

        market_elem = self._chrome_inst.find(By.ID, "market-yes")
        market_elem.click()

        preview_btn = self._chrome_inst.find(By.ID, "previewOrderBtn")
        preview_btn.click()

        time.sleep(2)

        self._check_error_msg(sym, amount, ActionType.BUY)

        place_order_btn = self._chrome_inst.waitForElementToLoad(By.ID, "placeOrderBtn")
        place_order_btn.click()

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

        time.sleep(2)

        self._check_error_msg(sym, amount, ActionType.SELL)

        place_order_btn = self._chrome_inst.waitForElementToLoad(By.ID, "placeOrderBtn")
        place_order_btn.click()

        # order_num = self._get_order_num()

        self._place_new_order()
        # return order_num

    def _check_error_msg(self, sym, amount, action: ActionType):
        try:
            self._chrome_inst.find(By.XPATH,
                                   "/html/body/div[3]/ap122489-ett-component/div/pvd3-modal[1]/s-root/div/div[2]/div/button")
            elem = self._chrome_inst.find(By.XPATH,
                                          '/html/body/div[3]/ap122489-ett-component/div/pvd3-modal[1]/s-root/div/div[2]/div/button')
            if elem.is_displayed():
                elem.click()
                raise ValueError(f'Fidelity {action.value} Error: {sym} - {amount}')
        except NoSuchElementException:  # no errors on fidelity
            pass

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def get_current_positions(self):
        self._chrome_inst.open("https://digital.fidelity.com/ftgw/digital/portfolio/positions")
        time.sleep(4)  # depends on internet speed but min 2 seconds for animation
        download_csv_positions = self._chrome_inst.waitForElementToLoad(By.XPATH,
                                                        '//*[@id="posweb-grid_top-presetviews_refresh_settings_share"]/div[2]/div[4]/button')
        download_csv_positions.click()
        import glob, pandas as pd # this code assumes that there are no csv files in the main trading directory which there shouldn't be
        file = glob.glob("/Users/sanathnair/Developer/trading/*.csv")[0]
        df = pd.read_csv(file)
        df = df.tail(-1) # delete the first row of the csv



if __name__ == '__main__':
    a = Fidelity("temp.csv")
    a.login()
    a.get_current_positions()
    # time.sleep(3)
    # a.sell("VRM", 1)
    # a.save_report()
