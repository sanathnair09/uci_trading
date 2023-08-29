import time
from datetime import datetime

import numpy as np
import pandas as pd
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys

from brokers import FIDELITY_LOGIN, FIDELITY_PASSWORD, BASE_PATH
from utils.broker import Broker
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
        self._chrome_inst.open("https://digital.fidelity.com/ftgw/digital/portfolio/positions")
        time.sleep(4)  # depends on internet speed but min 2 seconds for animation
        download_csv_positions = self._chrome_inst.waitForElementToLoad(By.XPATH,
                                                                        '//*[@id="posweb-grid_top-presetviews_refresh_settings_share"]/div[2]/div[4]/button')
        download_csv_positions.click()
        import glob, \
            pandas as pd  # this code assumes that there are no csv files in the main trading directory which there shouldn't be
        file = glob.glob("/Users/sanathnair/Developer/trading/*.csv")[0]
        df = pd.read_csv(file)
        df = df.tail(-1)  # delete the first row of the csv

    def get_trade_data(self):
        """
        gets the information from the https://digital.fidelity.com/ftgw/digital/portfolio/activity
        and stores it into a csv file to be used in the report generation
        :return:
        """
        self._chrome_inst.open('https://digital.fidelity.com/ftgw/digital/portfolio/activity')
        data_exists = input("Fidelity Continue? (Enter/n) ")

        if data_exists.upper() == "N":  # if you forgot to download data or run report early enough u can skip fidelity
            return None

        unopened = self._chrome_inst.get_page_source()

        try:  # super sus
            def get_xpath(row):
                return f'//*[@id="accountDetails"]/div/div[2]/div/new-tab-group/new-tab-group-ui/div[2]/activity-orders-panel/div/div/orders-grid-container/div/div[3]/activity-order-grid[1]/div/div[2]/activity-common-grid/div/table/tbody[{row}]/tr/td[5]/pvd3-button/s-root/button'

            x = 1
            while True:
                more_info = self._chrome_inst.find(By.XPATH, get_xpath(x))
                more_info.click()
                x += 1
        except:
            # done opening all the tabs
            pass

        opened = self._chrome_inst.get_page_source()

        unopened_df = Fidelity._handle_unopened_data(unopened)
        opened_df = Fidelity._handle_opened_data(opened)

        df = pd.merge(opened_df, unopened_df[['Symbol', 'Action']], left_on = 'Identifier',
                      right_index = True)

        df["Broker Executed"] = df["Broker Executed"].str.slice(stop = -3)
        df["Broker Executed"] = pd.to_datetime(df["Broker Executed"],
                                               format = '%I:%M:%S %p', utc = False)
        df["Price"] = df["Price"].str.slice(start = 1)
        df["Dollar Amt"] = df["Dollar Amt"].str.slice(start = 1)
        df["Broker Executed"] = df["Broker Executed"] + pd.Timedelta(hours = -3)

        return df[::-1]

    @staticmethod
    def _handle_unopened_data(unopened_html):
        df = pd.read_html(unopened_html)

        del df[1]  # remove the table at the bottom of page containing processed transactions
        df = df[0]  # get the remaining df and reassign
        df = df.drop(df.columns[[0, 2, 4]], axis = 1)  # remove Date, Nan, and Show Detail columns
        df.rename(columns = {1: 'Info', 3: "Price"}, inplace = True)
        df["Price"] = df["Price"].str.slice(start = 11).astype("float64")

        df_temp = df["Info"].str.split(expand = True)
        df = df.join(df_temp)
        df.rename(
            columns = {0: 'Action', 1: "Quantity", 2: "Shares",
                       3: "of", 4: "Symbol", 5: "at",
                       6: "type", 7: "when"}, inplace = True)
        df = df.drop(["Shares", "of", "at", "type", "when", "Info"], axis = 1)

        return df

    @staticmethod
    def _handle_opened_data(opened):
        df = pd.read_html(opened)

        del df[0]  # junk table
        del df[-1]  # table from bottom of page containing processed transactions

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
        splits_df = pd.DataFrame(res, columns = ["Date", "Broker Executed", "Price", "Quantity",
                                                 "Dollar Amt", "Identifier"])
        return splits_df

    def download_trade_data(self):
        from datetime import datetime
        df = self.get_trade_data()
        df.to_csv(
            BASE_PATH / f'data/fidelity_splits/fd_splits_{datetime.now().strftime("%m_%d")}.csv',
            index = False)


if __name__ == '__main__':
    a = Fidelity("temp.csv", BrokerNames.FD)
    a.login()
    a.download_trade_data()
    # time.sleep(3)
    # a.sell("VRM", 1)
    # a.save_report()
