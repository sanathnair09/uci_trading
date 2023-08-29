import time
from datetime import datetime

from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from utils.broker import Broker
from brokers import SCHWAB_LOGIN, SCHWAB_PASSWORD
from utils.selenium_helper import CustomChromeInstance
from utils.report.report import OrderType, ActionType, BrokerNames, StockData


class Schwab(Broker):
    def __init__(self, report_file, broker_name: BrokerNames):
        super().__init__(report_file, broker_name)
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open("https://client.schwab.com/Login/SignOn/CustomerCenterLogin.aspx")

    def _get_stock_data(self, sym: str):
        pass

    def buy(self, sym: str, amount: int):
        pre_stock_data = self._collect_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        try:
            self._market_buy(sym, amount)
            program_executed = datetime.now().strftime("%X:%f")
            post_stock_data = self._collect_stock_data(sym)

            self._add_report(program_submitted, program_executed, None, sym, ActionType.BUY,
                             amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                             False, None, None)
        except NoSuchElementException as e:
            if "sellAllHandle" in e.msg:
                logger.error(f"Schwab - Error buying {amount} {sym}")
            else:
                raise e

    def sell(self, sym: str, amount: int):
        pre_stock_data = self._collect_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        try:
            self._market_sell(sym, amount)
            program_executed = datetime.now().strftime("%X:%f")
            post_stock_data = self._collect_stock_data(sym)

            self._add_report(program_submitted, program_executed, None, sym, ActionType.SELL,
                             amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                             False, None, None)
        except NoSuchElementException as e:
            if "sellAllHandle" in e.msg:
                logger.error(f"Schwab - Error selling {amount} {sym}")
            else:
                raise e

    def _collect_stock_data(self, sym: str):
        symbol_elem = self._chrome_inst.waitForElementToLoad(By.XPATH, '//*[@id="_txtSymbol"]')
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)
        time.sleep(2)

        bid_price = self._chrome_inst.find(By.XPATH, '//*[@id="mcaio-bidlink"]/strong').text

        ask_price = self._chrome_inst.find(By.XPATH, '//*[@id="mcaio-asklink"]/strong').text

        last_price = self._chrome_inst.find(By.XPATH, '//*[@id="ctrl19"]/div[2]/div[1]/span/span')
        last_price = last_price.text[1:]

        volume = self._chrome_inst.find(By.XPATH, '//*[@id="ctrl19"]/div[5]/div[2]/span').text
        volume = volume.replace(',', '')

        return StockData(float(ask_price), float(bid_price), float(last_price), float(volume))

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

        amount_elem = self._chrome_inst.find(By.XPATH,
                                             '//*[@id="ordernumber01inputqty-stepper-input"]')
        self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

        self._chrome_inst.scroll(500)
        time.sleep(1)
        review_order_btn = self._chrome_inst.find(By.XPATH,
                                                  '//*[@id="mcaio-footer"]/div/div[2]/button[2]')
        review_order_btn.click()

        self._chrome_inst.scroll(350)
        time.sleep(1)  # wait for page to load
        place_order_btn = self._chrome_inst.waitForElementToLoad(By.XPATH,
                                                                 '//*[@id="mtt-place-button"]')
        place_order_btn.click()

        self._chrome_inst.open("https://client.schwab.com/app/trade/tom/#/trade")
        time.sleep(2)  # wait for trade page to load again

    def _market_sell(self, sym: str, amount: int):
        symbol_elem = self._chrome_inst.waitForElementToLoad(By.XPATH, '//*[@id="_txtSymbol"]')
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)
        time.sleep(2)
        # inherently sets the action type because it is selling all stocks for that symbol
        self._chrome_inst.find(By.XPATH, '//*[@id="mcaio-sellAllHandle"]').click()

        amount_elem = self._chrome_inst.find(By.XPATH,
                                             '//*[@id="ordernumber01inputqty-stepper-input"]')
        self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

        # order_type_dropdown = Select(self._chrome_inst.find(By.XPATH, '//*[@id="order-type"]'))
        # order_type_dropdown.select_by_visible_text("Market")
        self._chrome_inst.scroll(500)  # FIXME: scroll so button in view
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
        time.sleep(2)  # wait for trade page to load again

    def _limit_buy(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _limit_sell(self, sym: str, amount: int, limit_price: float):
        return NotImplementedError

    def _login(self, page):
        self._chrome_inst.switchToFrame("lmsSecondaryLogin")
        login_input_elem = self._chrome_inst.find(By.ID, "loginIdInput")
        self._chrome_inst.sendKeyboardInput(login_input_elem, SCHWAB_LOGIN)
        password_input_elem = self._chrome_inst.find(By.ID, "passwordInput")
        self._chrome_inst.sendKeyboardInput(password_input_elem, SCHWAB_PASSWORD)
        temp = self._chrome_inst.waitForElementToLoad(By.XPATH,
                                                      '/html/body/div/lms-app-root/section/div/div/section/lms-login-one-step-container/lms-login-one-step/section/div[1]/div[6]/div/select')
        select_elem = Select(temp)
        select_elem.select_by_visible_text(page)
        self._chrome_inst.waitToClick("btnLogin")
        time.sleep(2)  # TODO: use selenium wait

    def login(self):
        self._login("Trade Ticket")

    def download_trade_data(self, date):

        date_range = Select(
            self._chrome_inst.waitForElementToLoad(By.XPATH, '//*[@id="statements-daterange1"]')
        )
        date_range.select_by_visible_text("Custom")

        from_input = self._chrome_inst.find(By.XPATH,'//*[@id="calendar-FromDate"]')
        to_input = self._chrome_inst.find(By.XPATH, '//*[@id="calendar-ToDate"]')

        self._chrome_inst.sendKeyboardInput(from_input, date)
        self._chrome_inst.sendKeyboardInput(to_input, date)
        to_input.send_keys(Keys.RETURN)

        time.sleep(2)

        search = self._chrome_inst.find(By.XPATH, '//*[@id="btnSearch"]')
        search.click()

        download = self._chrome_inst.find(By.XPATH, '//*[@id="bttnExport"]/sdps-button')
        download.click()

        input("Approved Download?")


    def get_current_positions(self):
        pass


if __name__ == '__main__':
    # s = Schwab("temp.csv", BrokerNames.SB)
    #
    # s.login()
    #
    # time.sleep(3)
    pass
