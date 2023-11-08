import time
from datetime import datetime
from io import StringIO

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys

from brokers import FIDELITY_LOGIN, FIDELITY_PASSWORD, BASE_PATH
from utils.broker import Broker
from utils.misc import save_content_to_file
from utils.report.report import BrokerNames, OrderType, ActionType, StockData
from utils.selenium_helper import CustomChromeInstance
from selenium.webdriver.common.by import By


#
class Fidelity(Broker):
    def __init__(self, report_file, broker_name: BrokerNames):
        super().__init__(report_file, broker_name)
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open("https://digital.fidelity.com/prgw/digital/login/full-page")

    def login(self):
        try:
            login_input_elem = self._chrome_inst.find(By.XPATH, '//*[@id="userId-input"]')
            self._chrome_inst.sendKeyboardInput(login_input_elem, FIDELITY_LOGIN)
            password_input_elem = self._chrome_inst.find(By.ID, "password")
            self._chrome_inst.sendKeyboardInput(password_input_elem, FIDELITY_PASSWORD)
            self._chrome_inst.waitToClick("fs-login-button")
            time.sleep(5)  # will have to play with time depending on your internet speeds
            self._chrome_inst.open(
                "https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry")
            time.sleep(1)
        except:
            login_input_elem = self._chrome_inst.find(By.XPATH, '//*[@id="dom-username-input"]')
            self._chrome_inst.sendKeyboardInput(login_input_elem, FIDELITY_LOGIN)
            password_input_elem = self._chrome_inst.find(By.XPATH, '//*[@id="dom-pswd-input"]')
            self._chrome_inst.sendKeyboardInput(password_input_elem, FIDELITY_PASSWORD)
            login_button = self._chrome_inst.find(By.XPATH, '//*[@id="dom-login-button"]')
            login_button.click()
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
                         amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None)

    def sell(self, sym: str, amount: int):
        pre_stock_data = self._get_stock_data(sym)
        program_submitted = datetime.now().strftime("%X:%f")
        self._market_sell(sym, amount)
        program_executed = datetime.now().strftime("%X:%f")
        post_stock_data = self._get_stock_data(sym)

        self._add_report(program_submitted, program_executed, None, sym, ActionType.SELL,
                         amount, "", "", pre_stock_data, post_stock_data, OrderType.MARKET,
                         False, None, None)

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
        """
        used to automtically sell left over positions
        :return: list of (symbol, amount)
        """
        self._chrome_inst.open("https://digital.fidelity.com/ftgw/digital/portfolio/positions")
        time.sleep(4)  # depends on internet speed but min 2 seconds for animation
        download_csv_positions = self._chrome_inst.waitForElementToLoad(By.XPATH,
                                                                        '//*[@id="posweb-grid_top-presetviews_refresh_settings_share"]/div[2]/div[4]/button')
        download_csv_positions.click()
        time.sleep(5) # wait for file to download
        import glob
        # this code assumes that there are no csv files in the main trading directory which there shouldn't be
        file = glob.glob("/Users/sanathnair/Developer/trading/data/*.csv")[0]
        df = pd.read_csv(file)
        df = df.drop(df.index[[0, -1, -2, -3, -4]]) # only keep rows with stock info
        positions = [(sym, quantity) for sym, quantity in df[["Symbol", "Quantity"]].to_numpy()]
        self._chrome_inst.open("https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry")
        time.sleep(3)
        return positions


    def get_trade_data(self):
        """
                gets the information from the https://digital.fidelity.com/ftgw/digital/portfolio/activity
                and stores it into a csv file to be used in the report generation
                :return:
                """
        self._chrome_inst.open('https://digital.fidelity.com/ftgw/digital/portfolio/activity')
        data_exists = input(
            "Fidelity (load more results and close assitant bubble in bottom right corner) (Enter/n) ")

        if data_exists.upper() == "N":  # if you forgot to download data or run report early enough u can skip fidelity
            return None

        unopened = self._chrome_inst.get_page_source()
        try:  # super sus
            def get_xpath(row):
                return f'//*[@id="accountDetails"]/div/div[2]/div/new-tab-group/new-tab-group-ui/div[2]/activity-orders-shell/div/ap143528-portsum-dashboard-activity-orders-home-root/div/div/div/account-activity-container/div/div[3]/activity-list[1]/div/div[{row}]'

            x = 3
            while True:
                more_info = self._chrome_inst.find(By.XPATH, get_xpath(x))
                more_info.click()
                x += 1
        except Exception as e:
            # done opening all the tabs
            pass

        opened = self._chrome_inst.get_page_source()

        return self.parse_trade_data(unopened, opened)

    @staticmethod
    def parse_trade_data(unopened, opened):
        unopened_df = Fidelity._handle_unopened_data(unopened)
        opened_df = Fidelity._handle_opened_data(opened)
        df = pd.merge(left = opened_df, right = unopened_df, left_on = "Identifier",
                      right_index = True)

        df["Broker Executed"] = pd.to_datetime(df["Broker Executed"], format = '%I:%M:%S %p ET',
                                               utc = False) - pd.Timedelta(hours = 3)
        df["Broker Executed"] = df["Broker Executed"].dt.strftime('%I:%M:%S')
        df["Price"] = df["Price"].str.slice(start = 1)
        df["Dollar Amt"] = df["Dollar Amt"].str.slice(start = 1)

        new_df = df[::-1]

        date = datetime.now().strftime("%m_%d")
        new_df.to_csv(BASE_PATH / f'data/fidelity/fd_splits_{date}.csv', index = False)

        return new_df

    @staticmethod
    def _handle_unopened_data(unopened_html):
        unopened_df = pd.DataFrame()
        soup = BeautifulSoup(unopened_html, 'html.parser')
        class_to_find = "pvd-grid__grid pvd-grid__grid--default-column-span-12"
        data = soup.find_all(class_ = class_to_find)
        for row in data:
            text = row.get_text(strip = True).split()
            if len(text) != 8:
                break
            row_info = pd.Series([text[0], text[4]], index = ["Action", "Symbol"])
            unopened_df = pd.concat([unopened_df, row_info.to_frame().T], ignore_index = True)

        unopened_df = unopened_df[
            (unopened_df["Action"] == "Buy") | (unopened_df["Action"] == "Sell")]

        return unopened_df

    @staticmethod
    def _handle_opened_data(opened):
        df = pd.read_html(StringIO(opened))

        # get the data from the individual split dfs and put them into a list
        prices = []
        for idx, temp in enumerate(df):
            splits = temp.iloc[:-1].to_numpy()
            length = splits.shape[0]
            identifier = np.empty((length, 1))
            identifier.fill(idx)
            updated = np.hstack((splits, identifier))
            prices.append(updated)

        # combine all the rows into one
        res = prices[0]
        for x in prices[1:]:
            res = np.append(res, x, axis = 0)

        # create a df with split info
        splits_df = pd.DataFrame(res, columns = ["Date", "Broker Executed", "Price", "Size",
                                                 "Dollar Amt", "Identifier"])

        splits_df['Split'] = splits_df['Identifier'].duplicated(keep = False)

        return splits_df

    def download_trade_data(self):
        from datetime import datetime
        df = self.get_trade_data()
        if isinstance(df, pd.DataFrame):
            df.to_csv(
                BASE_PATH / f'data/fidelity/fd_splits_{datetime.now().strftime("%m_%d")}.csv',
                index = False)


if __name__ == '__main__':
    a = Fidelity("temp.csv", BrokerNames.FD)
    a.login()
    a.download_trade_data()
    pass
