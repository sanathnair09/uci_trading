import time
from datetime import datetime
from io import StringIO

import pandas as pd
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from utils.broker import Broker
from brokers import SCHWAB_LOGIN, SCHWAB_PASSWORD
from utils.misc import convert_to_float
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
            self._error_count += 1
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
            self._error_count += 1
            raise e

    def _collect_stock_data(self, sym: str):
        symbol_elem = self._chrome_inst.find(By.XPATH, '//*[@id="_txtSymbol"]')
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)
        time.sleep(2)

        bid_price = self._chrome_inst.find(By.XPATH, '//*[@id="mcaio-bidlink"]/strong').text

        ask_price = self._chrome_inst.find(By.XPATH, '//*[@id="mcaio-asklink"]/strong').text

        last_price = self._chrome_inst.find(By.XPATH, '//*[@id="ctrl19"]/div[2]/div[1]/span/span')
        last_price = last_price.text[1:]

        volume = self._chrome_inst.find(By.XPATH, '//*[@id="ctrl19"]/div[4]/div[1]/div/span').text
        volume = volume.replace(',', '')

        return StockData(convert_to_float(ask_price), convert_to_float(bid_price),
                         convert_to_float(last_price), convert_to_float(volume))

    def _market_buy(self, sym: str, amount: int):
        symbol_elem = self._chrome_inst.find(By.XPATH, '//*[@id="_txtSymbol"]')
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)
        time.sleep(2)
        action_dropdown = Select(
            self._chrome_inst.find(By.XPATH, '//*[@id="_action"]'))
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
        place_order_btn = self._chrome_inst.find(By.XPATH, '//*[@id="mtt-place-button"]')
        place_order_btn.click()

        time.sleep(1)
        new_order_btn = self._chrome_inst.find(By.XPATH,
                                               '//*[@id="mcaio-footer"]/div/div/button[3]')
        new_order_btn.click()
        # self._chrome_inst.open("https://client.schwab.com/app/trade/tom/#/trade")
        time.sleep(2)  # wait for trade page to load again

    def _market_sell(self, sym: str, amount: int):
        symbol_elem = self._chrome_inst.find(By.XPATH, '//*[@id="_txtSymbol"]')
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
        place_order_btn = self._chrome_inst.find(By.XPATH,
                                                 '//*[@id="mtt-place-button"]')
        place_order_btn.click()

        time.sleep(1)
        new_order_btn = self._chrome_inst.find(By.XPATH,
                                               '//*[@id="mcaio-footer"]/div/div/button[3]')
        new_order_btn.click()
        # self._chrome_inst.open("https://client.schwab.com/app/trade/tom/#/trade")
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
        temp = self._chrome_inst.find(By.XPATH,
                                      '/html/body/div/lms-app-root/section/div/div/section/lms-login-one-step-container/lms-login-one-step/section/div[1]/div[6]/div/select')
        select_elem = Select(temp)
        select_elem.select_by_visible_text(page)
        self._chrome_inst.waitToClick("btnLogin")
        while self._chrome_inst.current_url() != "https://client.schwab.com/app/trade/tom/#/trade":
            pass
        time.sleep(5)  # TODO: use selenium wait
        self._chrome_inst.resetFrame()

    def login(self):
        self._login("Trade Ticket")

    def download_trade_data(self, date):

        date_range = Select(
            self._chrome_inst.find(By.XPATH, '//*[@id="statements-daterange1"]')
        )
        date_range.select_by_visible_text("Custom")

        from_input = self._chrome_inst.find(By.XPATH, '//*[@id="calendar-FromDate"]')
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

    def resolve_errors(self):
        if self._error_count > 0:
            self._chrome_inst.refresh()
            self._error_count = 0

    def get_current_positions(self) -> list[tuple[str, float]]:
        """
        used to automtically sell left over positions
        :return: list of (symbol, amount)
        """
        self._chrome_inst.open("https://client.schwab.com/app/accounts/positions/#/")
        positions = []
        try:
            time.sleep(5)
            page_source = self._chrome_inst.get_page_source()
            df = pd.read_html(StringIO(page_source))
            df = df[0]
            df = df.drop(df.index[[0, -1, -2, -3, -4, -5]])
            positions = df[["Symbol", "Quantity"]].to_numpy()
            positions = [(x[0], float(x[1])) for x in positions]
        except Exception as e:
            print("Error getting current positions", e)
        self._chrome_inst.open("https://client.schwab.com/app/trade/tom/#/trade")
        time.sleep(3)
        return positions


if __name__ == '__main__':
    s = Schwab("temp.csv", BrokerNames.SB)
    s.login()
    s.buy("VRM", 1)
    time.sleep(1)
    s.sell("VRM", 1)
    pass
