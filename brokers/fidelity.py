from pathlib import Path
import time
from datetime import datetime
from io import StringIO
from typing import Any, Optional, Union, cast

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By

from brokers import FIDELITY_LOGIN, FIDELITY_PASSWORD, BASE_PATH
from utils.broker import Broker, OptionOrder, StockOrder
from utils.market_data import MarketData
from utils.report.report import (
    BrokerNames,
    OptionReportEntry,
    OptionType,
    OrderType,
    ActionType,
    ReportEntry,
    StockData,
    OptionData,
)
from utils.selenium_helper import CustomChromeInstance
from utils.util import convert_date


#
class Fidelity(Broker):

    def __init__(
        self,
        report_file: Path,
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        super().__init__(report_file, broker_name, option_report_file)
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open(
            "https://digital.fidelity.com/prgw/digital/login/full-page"
        )

    def login(self) -> None:
        login_input_elem = self._chrome_inst.find(
            By.XPATH, '//*[@id="dom-username-input"]'
        )
        self._chrome_inst.sendKeyboardInput(login_input_elem, FIDELITY_LOGIN)
        time.sleep(1)
        password_input_elem = self._chrome_inst.find(
            By.XPATH, '//*[@id="dom-pswd-input"]'
        )
        self._chrome_inst.sendKeyboardInput(password_input_elem, FIDELITY_PASSWORD)
        time.sleep(1)
        login_button = self._chrome_inst.find(By.XPATH, '//*[@id="dom-login-button"]')
        login_button.click()
        time.sleep(5)  # will have to play with time depending on your internet speeds
        self._chrome_inst.open(
            "https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry"
        )
        input("Finished logging in? (Enter/n) ")

    def _get_stock_data(self, sym: str) -> StockData:
        symbol_elem = self._chrome_inst.waitForElementToLoad(
            By.ID, "eq-ticket-dest-symbol"
        )
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)

        time.sleep(1)

        bid_price = self._chrome_inst.find(
            By.XPATH, '//*[@id="quote-panel"]/div/div[2]/div[1]/div/span/span'
        ).text.replace(",", "")

        ask_price = self._chrome_inst.find(
            By.XPATH, '//*[@id="quote-panel"]/div/div[2]/div[2]/div/span/span'
        ).text.replace(",", "")

        volume = self._chrome_inst.find(
            By.XPATH, '//*[@id="quote-panel"]/div/div[2]/div[3]/div/span'
        ).text.replace(",", "")
        try:
            quote = self._chrome_inst.find(
                By.XPATH,
                '//*[@id="ett-more-quote-info"]/div/div/div/div/div[2]/div[1]/div[2]/span',
            ).text
        except NoSuchElementException:
            self._chrome_inst.find(By.ID, "ett-more-less-quote-link").click()
            time.sleep(0.5)
            quote = self._chrome_inst.find(
                By.XPATH,
                '//*[@id="ett-more-quote-info"]/div/div/div/div/div[2]/div[1]/div[2]/span',
            ).text
        quote = quote.replace(",", "")
        symbol_elem.send_keys(Keys.BACKSPACE * 5)
        return StockData(
            float(ask_price), float(bid_price), float(quote[1:]), float(volume)
        )

    def buy(self, order: StockOrder) -> None:
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = self._get_current_time()
        try:
            self._market_buy(order)
        except Exception as e:
            raise e
        program_executed = self._get_current_time()
        post_stock_data = self._get_stock_data(order.sym)

        self._save_report(
            order.sym,
            ActionType.BUY,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
            quantity=order.quantity,
        )

    def sell(self, order: StockOrder) -> None:
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = self._get_current_time()
        try:
            self._market_sell(order)
        except Exception as e:
            raise e
        program_executed = self._get_current_time()
        post_stock_data = self._get_stock_data(order.sym)

        self._save_report(
            order.sym,
            ActionType.SELL,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
            quantity=order.quantity,
        )

    def buy_option(self, order: OptionOrder) -> None:
        self._change_order_type(ActionType.OPEN)  # change UI to option trading

        pre_stock_data = self._get_option_data(order)
        program_submitted = self._get_current_time()

        if order.option_type == OptionType.CALL:
            self._buy_call_option(order)
        else:
            self._buy_put_option(order)

        program_executed = self._get_current_time()
        post_stock_data = self._get_option_data(order)

        self._save_option_report(
            order,
            ActionType.BUY,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
        )

        self._change_order_type(ActionType.BUY)  # change UI back to stock trading

    def sell_option(self, order: OptionOrder) -> None:
        self._change_order_type(ActionType.OPEN)  # change UI to option trading

        pre_stock_data = self._get_option_data(order)
        program_submitted = self._get_current_time()

        if order.option_type == OptionType.CALL:
            self._sell_call_option(order)
        else:
            self._sell_put_option(order)

        program_executed = self._get_current_time()
        post_stock_data = self._get_option_data(order)

        self._save_option_report(
            order,
            ActionType.SELL,
            program_submitted,
            program_executed,
            pre_stock_data,
            post_stock_data,
        )

        self._change_order_type(ActionType.BUY)  # change UI back to stock trading

    def _market_buy(self, order: StockOrder) -> None:
        self._perform_order(order.sym, order.quantity, ActionType.BUY, OrderType.MARKET)

    def _market_sell(self, order: StockOrder) -> None:
        self._perform_order(
            order.sym, order.quantity, ActionType.SELL, OrderType.MARKET
        )

    def _buy_call_option(self, order: OptionOrder) -> None:
        self._option_helper(
            order.sym, OptionType.CALL, order.strike, order.expiration, ActionType.OPEN
        )

    def _sell_call_option(self, order: OptionOrder) -> None:
        self._option_helper(
            order.sym, OptionType.CALL, order.strike, order.expiration, ActionType.CLOSE
        )

    def _buy_put_option(self, order: OptionOrder) -> None:
        self._option_helper(
            order.sym, OptionType.PUT, order.strike, order.expiration, ActionType.OPEN
        )

    def _sell_put_option(self, order: OptionOrder) -> None:
        self._option_helper(
            order.sym, OptionType.PUT, order.strike, order.expiration, ActionType.CLOSE
        )

    def _option_helper(
        self,
        sym: str,
        option_type: OptionType,
        strike_price: str,
        expiration_date: str,
        action: ActionType,
    ) -> None:
        self._choose_option_symbol(sym)
        self._choose_option_action(action)
        self._set_option_quantity()
        self._chose_option_order_type(option_type)
        self._set_option_expiration(expiration_date)
        self._set_strike_price(strike_price)
        self._set_option_order_type()
        self._set_cash_order()
        self._preview_option_order()
        self._place_option_order()
        self._place_another_option_order()

    def _change_order_type(self, actionType: ActionType) -> None:
        if actionType == ActionType.OPEN or actionType == ActionType.CLOSE:
            self._chrome_inst.open(
                "https://digital.fidelity.com/ftgw/digital/trade-options?ACCOUNT=X30124290&&FULL_BANNER=Y&TIME_IN_FORCE=D&ORDER_TYPE=O&CURRENT_PAGE=TradeOption&DEST_TRADE=Y"
            )
        else:
            self._chrome_inst.open(
                "https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry"
            )
        time.sleep(2)

    def _choose_option_symbol(self, sym: str) -> None:
        symbol = self._chrome_inst.find(By.XPATH, '//*[@id="symbol_search_label"]')
        symbol.click()
        time.sleep(1)
        symbol = self._chrome_inst.find(By.XPATH, '//*[@id="symbol_search"]')
        self._chrome_inst.sendKeyboardInput(symbol, sym)
        symbol.send_keys(Keys.RETURN)
        time.sleep(1)

    def _choose_option_action(self, action_type: ActionType) -> None:
        action = self._chrome_inst.find(By.XPATH, '//*[@id="action_dropdown"]/span[5]')
        action.click()
        if action_type == ActionType.OPEN:
            self._chrome_inst.find(
                By.XPATH,
                '//*[@id="init-form"]/div[2]/trade-option-init/div/div[3]/div/div[1]/div/div/button[1]',
            ).click()
        else:  # close
            self._chrome_inst.find(
                By.XPATH,
                '//*[@id="init-form"]/div[2]/trade-option-init/div/div[3]/div/div[1]/div/div/button[4]',
            ).click()

    def _set_option_quantity(self) -> None:
        quantity = self._chrome_inst.find(By.XPATH, '//*[@id="dest-quantity"]')
        self._chrome_inst.sendKeyboardInput(quantity, "1")

    def _chose_option_order_type(self, optionType: OptionType) -> None:
        if optionType == OptionType.CALL:
            self._chrome_inst.find(
                By.XPATH,
                '//*[@id="init-form"]/div[2]/trade-option-init/div/div[3]/div/div[3]/div/input[1]',
            ).click()
        else:  # PUT
            self._chrome_inst.find(
                By.XPATH,
                '//*[@id="init-form"]/div[2]/trade-option-init/div/div[3]/div/div[3]/div/input[2]',
            ).click()

    def _set_option_expiration(self, expiration_date: str) -> None:
        dropdown = self._chrome_inst.find(By.XPATH, '//*[@id="exp_dropdown"]')
        dropdown.click()
        time.sleep(1)
        date = convert_date(expiration_date, "%b %d, %Y")
        expiration_entry = self._chrome_inst.find(
            By.XPATH,
            f'//*[@id="init-form"]/div[2]/trade-option-init/div/div[3]/div/div[4]/div/div/button/span[contains(text(), "{date}")]',
        )
        self._chrome_inst.scroll_to_element(expiration_entry)
        expiration_entry.click()
        time.sleep(2)

    def _set_strike_price(self, strike: str) -> None:
        dropdown = self._chrome_inst.find(By.XPATH, '//*[@id="strike_dropdown"]')
        dropdown.click()
        time.sleep(1)
        strike_entry = self._chrome_inst.find(
            By.XPATH,
            f'//*[@id="init-form"]/div[2]/trade-option-init/div/div[3]/div/div[5]/div/div/button[contains(text(), "{strike}")]',
        )
        self._chrome_inst.scroll_to_element(strike_entry)
        strike_entry.click()

    def _set_option_order_type(self) -> None:
        dropdown = self._chrome_inst.find(By.XPATH, '//*[@id="orderType_dropdown"]')
        dropdown.click()
        market = self._chrome_inst.find(
            By.XPATH,
            '//*[@id="init-form"]/div[2]/trade-option-init/div/div[6]/div[1]/div/div/button[1]',
        )
        market.click()

    def _set_cash_order(self) -> None:
        dropdown = self._chrome_inst.find(By.XPATH, '//*[@id="tradeType_dropdown"]')
        dropdown.click()
        cash = self._chrome_inst.find(
            By.XPATH,
            '//*[@id="init-form"]/div[2]/trade-option-init/div/div[6]/div[3]/div/div/button[2]',
        )
        cash.click()

    def _preview_option_order(self) -> None:
        time.sleep(1)
        preview = self._chrome_inst.find(By.XPATH, '//*[@id="previewButton"]')
        preview.click()
        time.sleep(2)

    def _place_option_order(self) -> None:
        place_order = self._chrome_inst.find(By.XPATH, '//*[@id="dest-place-button"]')
        place_order.click()
        time.sleep(1)

    def _place_another_option_order(self) -> None:
        another = self._chrome_inst.find(By.XPATH, '//*[@id="place-new-order"]')
        another.click()

    def _perform_order(
        self, sym: str, amount: float, action: ActionType, order_type: OrderType
    ) -> None:
        self._choose_stock(sym)
        self._set_action(action)
        self._set_amount(amount)
        self._set_order_type(order_type)
        self._preview_order()
        time.sleep(2)
        self._check_error_msg(sym, amount, action)
        time.sleep(1)
        self._place_order()
        self._place_new_order()

    def _choose_stock(self, sym: str) -> None:
        symbol_elem = self._chrome_inst.waitForElementToLoad(
            By.ID, "eq-ticket-dest-symbol"
        )
        symbol_elem.send_keys(Keys.BACKSPACE * 5)
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN)

        time.sleep(2)

    def _set_action(self, action: ActionType) -> None:
        if action == ActionType.BUY:
            buy_elem = self._chrome_inst.find(By.ID, "action-buy")
            buy_elem.click()
        else:  # SELL
            sell_elem = self._chrome_inst.find(By.ID, "action-sell")
            sell_elem.click()

    def _set_amount(self, amount: float) -> None:
        amount_elem = self._chrome_inst.find(By.XPATH, '//*[@id="eqt-shared-quantity"]')
        self._chrome_inst.sendKeyboardInput(amount_elem, str(amount))

    def _set_order_type(self, order_type: OrderType) -> None:
        if order_type == OrderType.MARKET:
            market_elem = self._chrome_inst.find(By.ID, "market-yes")
            market_elem.click()

    def _preview_order(self) -> None:
        preview_btn = self._chrome_inst.find(By.ID, "previewOrderBtn")
        preview_btn.click()

    def _place_order(self) -> None:
        place_order_btn = self._chrome_inst.waitForElementToLoad(By.ID, "placeOrderBtn")
        place_order_btn.click()

    def _place_new_order(self) -> None:
        place_new_order_btn = self._chrome_inst.waitForElementToLoad(
            By.ID, "eq-ticket__enter-new-order"
        )
        place_new_order_btn.click()

    def _check_error_msg(self, sym: str, amount: float, action: ActionType) -> None:
        try:
            self._chrome_inst.find(
                By.XPATH,
                "/html/body/div[3]/ap122489-ett-component/div/pvd3-modal[1]/s-root/div/div[2]/div/button",
            )
            elem = self._chrome_inst.find(
                By.XPATH,
                "/html/body/div[3]/ap122489-ett-component/div/pvd3-modal[1]/s-root/div/div[2]/div/button",
            )
            if elem.is_displayed():
                elem.click()
                raise ValueError(f"Fidelity {action.value} Error: {sym} - {amount}")
        except NoSuchElementException:  # no errors on fidelity
            pass

    def _limit_buy(self, order: StockOrder) -> Any:
        return NotImplementedError

    def _limit_sell(self, order: StockOrder) -> Any:
        return NotImplementedError

    def _get_option_data(self, order: OptionOrder) -> OptionData:
        return MarketData.get_option_data(order)

    def _save_report(
        self,
        sym: str,
        action_type: ActionType,
        program_submitted: str,
        program_executed: str,
        pre_stock_data: StockData,
        post_stock_data: StockData,
        **kwargs: Union[str, float],
    ) -> None:

        self._add_report_to_file(
            ReportEntry(
                program_submitted,
                program_executed,
                None,  # broker executed time added during post processing
                sym,
                action_type,
                cast(float, kwargs["quantity"]),
                None,
                None,
                pre_stock_data,
                post_stock_data,
                OrderType.MARKET,
                False,
                None,
                None,
                BrokerNames.FD,
            )
        )

        self._save_report_to_file()

    def _save_option_report(
        self,
        order: OptionOrder,
        action_type: ActionType,
        program_submitted: str,
        program_executed: str,
        pre_stock_data: OptionData,
        post_stock_data: OptionData,
        **kwargs: str,
    ) -> None:
        self._add_option_report_to_file(
            OptionReportEntry(
                program_submitted,
                program_executed,
                None,  # broker executed time added during post processing``
                order.sym,
                order.strike,
                order.option_type,
                order.expiration,
                action_type,
                None,  # fidelity price added during post processing
                pre_stock_data,
                post_stock_data,
                OrderType.MARKET,
                None,  # venue info not available
                None,  # order id not available
                None,  # activity id not available
                BrokerNames.FD,
            )
        )

        self._save_option_report_to_file()

    def get_current_positions(self) -> tuple[list[StockOrder], list[OptionOrder]]:
        """
        used to automatically sell left over positions
        :return: list of (symbol, amount)
        """
        self._chrome_inst.open(
            "https://digital.fidelity.com/ftgw/digital/portfolio/positions"
        )
        # time.sleep(4)  # depends on internet speed but min 2 seconds for animation
        input("Finished loading positions? (Enter/n) ")
        download_csv_positions = self._chrome_inst.waitForElementToLoad(
            By.XPATH,
            '//*[@id="posweb-grid_top-presetviews_refresh_settings_share"]/div[2]/div[4]/button',
        )
        download_csv_positions.click()
        time.sleep(5)  # wait for file to download

        file = (
            BASE_PATH
            / f'data/Portfolio_Positions_{datetime.now().strftime("%b-%d-%Y")}.csv'
        )
        df = pd.read_csv(file)
        df = df.drop(df.index[[0, -1, -2, -3, -4]])  # only keep rows with stock info
        positions = [
            StockOrder(sym, quantity)
            for sym, quantity in df[["Symbol", "Quantity"]].to_numpy()
        ]
        self._chrome_inst.open(
            "https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry"
        )
        time.sleep(3)

        import os

        os.remove(file)

        return positions, []

    def get_trade_data(self) -> pd.DataFrame:
        """
        gets the information from the https://digital.fidelity.com/ftgw/digital/portfolio/activity
        and stores it into a csv file to be used in the report generation
        :return:
        """

        def save_string_to_file(content: str, filename: str) -> None:
            with open(filename, "w") as file:
                file.write(content)

        self._chrome_inst.open(
            "https://digital.fidelity.com/ftgw/digital/portfolio/activity"
        )
        _ = input("Fidelity (load more results)?")

        unopened = self._chrome_inst.get_page_source()
        try:  # super sus

            def get_xpath(row: int) -> str:
                return f'//*[@id="accountDetails"]/div/div[2]/div/new-tab-group/new-tab-group-ui/div[2]/activity-orders-shell/div/ap143528-portsum-dashboard-activity-orders-home-root/div/div/account-activity-container/div/div[2]/activity-list[1]/div/div[3]/div[{row}]/div/div[1]'

            x = 1
            while True:
                more_info = self._chrome_inst.find(By.XPATH, get_xpath(x))
                more_info.click()
                x += 1
        except Exception as e:
            # done opening all the tabs
            pass

        opened = self._chrome_inst.get_page_source()

        # save_string_to_file(unopened, "unopened.html")
        # save_string_to_file(opened, "opened.html")

        return self.parse_trade_data(unopened, opened)

    @staticmethod
    def parse_trade_data(unopened: str, opened: str) -> pd.DataFrame:
        unopened_df = Fidelity._handle_unopened_data(unopened)
        opened_df = Fidelity._handle_opened_data(opened)
        df = pd.merge(
            left=opened_df, right=unopened_df, left_on="Identifier", right_index=True
        )

        df["Broker Executed"] = pd.to_datetime(
            df["Broker Executed"], format="%I:%M:%S %p ET", utc=False
        ) - pd.Timedelta(hours=3)
        df["Broker Executed"] = df["Broker Executed"].dt.strftime("%I:%M:%S")
        df["Price"] = df["Price"].str.slice(start=1)
        df["Dollar Amt"] = df["Dollar Amt"].str.slice(start=1)

        new_df = df[::-1]

        date = datetime.now().strftime("%m_%d")
        new_df.to_csv(BASE_PATH / f"data/fidelity/fd_splits_{date}.csv", index=False)

        return new_df

    @staticmethod
    def _create_row(
        sym: str,
        action: str,
        strike: Optional[str] = None,
        expiration: Optional[str] = None,
        option_type: Optional[str] = None,
    ) -> pd.Series:
        return pd.Series(
            [sym, action, strike, expiration, option_type],
            index=["Symbol", "Action", "Strike", "Expiration", "Option Type"],
        )

    @staticmethod
    def _handle_unopened_data(unopened_html: str) -> pd.DataFrame:
        unopened_df = pd.DataFrame()
        soup = BeautifulSoup(unopened_html, "html.parser")
        class_to_find = "pvd-grid__grid pvd-grid__grid--default-column-span-12"
        data = soup.find_all(class_=class_to_find)
        for row in data:
            text = row.get_text(strip=True).split()
            if text[3] != "Contract":
                row_info = Fidelity._create_row(text[4], text[0])
            else:
                row_info = Fidelity._create_row(
                    text[4],
                    text[0],
                    strike=text[8],
                    expiration=f"{text[5]}-{text[6]}-{text[7]}",
                    option_type=text[9],
                )
            unopened_df = pd.concat(
                [unopened_df, row_info.to_frame().T], ignore_index=True
            )

        unopened_df = unopened_df[
            (unopened_df["Action"] == "Buy") | (unopened_df["Action"] == "Sell")
        ]

        return unopened_df

    @staticmethod
    def _handle_opened_data(opened: str) -> pd.DataFrame:
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
            res = np.append(res, x, axis=0)

        # create a df with split info
        splits_df = pd.DataFrame(
            res,
            columns=[
                "Date",
                "Broker Executed",
                "Price",
                "Size",
                "Dollar Amt",
                "Identifier",
            ],
        )

        splits_df["Split"] = splits_df["Identifier"].duplicated(keep=False)

        return splits_df

    def download_trade_data(self) -> None:
        from datetime import datetime

        df = self.get_trade_data()
        if isinstance(df, pd.DataFrame):
            df.to_csv(
                BASE_PATH
                / f'data/fidelity/fd_splits_{datetime.now().strftime("%m_%d")}.csv',
                index=False,
            )


if __name__ == "__main__":
    a = Fidelity(Path("temp.csv"), BrokerNames.FD, Path("temp_option.csv"))
    a.login()
    a.download_trade_data()
    pass
