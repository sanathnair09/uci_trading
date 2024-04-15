from pathlib import Path
import time
from datetime import datetime
from io import StringIO
from typing import Any, Optional, Union, cast

import pandas as pd
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from utils.broker import Broker, OptionOrder, StockOrder
from brokers import SCHWAB_LOGIN, SCHWAB_PASSWORD
from utils.market_data import MarketData
from utils.util import convert_to_float, parse_option_string
from utils.selenium_helper import CustomChromeInstance
from utils.report.report import (
    NULL_STOCK_DATA,
    OptionReportEntry,
    OptionType,
    OrderType,
    ActionType,
    BrokerNames,
    ReportEntry,
    StockData,
    OptionData,
)


class Schwab(Broker):
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
        **kwargs: Union[float, str],
    ) -> None:
        self._add_report_to_file(
            ReportEntry(
                program_submitted,
                program_executed,
                None,
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
                BrokerNames.SB,
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
                None,
                order.sym,
                order.strike,
                order.option_type,
                order.expiration,
                action_type,
                None,
                pre_stock_data,
                post_stock_data,
                OrderType.MARKET,
                None,
                None,
                None,
                BrokerNames.SB,
            )
        )

        self._save_option_report_to_file()

    def __init__(
        self,
        report_file: Path,
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        super().__init__(report_file, broker_name, option_report_file)
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open(
            "https://client.schwab.com/Login/SignOn/CustomerCenterLogin.aspx"
        )

    def _get_stock_data(self, sym: str) -> StockData:
        self._set_symbol(sym)

        bid_price = self._chrome_inst.find(
            By.XPATH, '//*[@id="mcaio-bidlink"]/strong'
        ).text

        ask_price = self._chrome_inst.find(
            By.XPATH, '//*[@id="mcaio-asklink"]/strong'
        ).text

        last_price_t = self._chrome_inst.find(
            By.XPATH, '//*[@id="ctrl19"]/div[2]/div[1]/span/span'
        )
        last_price = last_price_t.text[1:]

        volume = self._chrome_inst.find(
            By.XPATH, '//*[@id="ctrl19"]/div[4]/div[1]/div/span'
        ).text
        volume = volume.replace(",", "")

        return StockData(
            convert_to_float(ask_price),  # type: ignore
            convert_to_float(bid_price),  # type: ignore
            convert_to_float(last_price),  # type: ignore
            convert_to_float(volume),  # type: ignore
        )

    def buy(self, order: StockOrder) -> None:
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = self._get_current_time()
        try:
            self._market_buy(order)
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
        except NoSuchElementException as e:
            if "sellAllHandle" in e.msg:  # type: ignore
                logger.error(f"Schwab - Error buying {order.quantity} {order.sym}")

    def sell(self, order: StockOrder) -> None:
        pre_stock_data = self._get_stock_data(order.sym)
        program_submitted = self._get_current_time()
        try:
            self._market_sell(order)
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
        except NoSuchElementException as e:
            if "sellAllHandle" in e.msg:  # type: ignore
                logger.error(f"Schwab - Error selling {order.quantity} {order.sym}")

    def _market_buy(self, order: StockOrder) -> None:
        self._set_trading_type(order)
        self._set_symbol(order.sym)
        self._set_action(ActionType.BUY)
        amount_elem = self._chrome_inst.find(
            By.XPATH, '//*[@id="ordernumber01inputqty-stepper-input"]'
        )
        self._chrome_inst.sendKeyboardInput(amount_elem, str(order.quantity))
        self._chrome_inst.scroll(500)
        time.sleep(1)
        self._review_order()
        self._chrome_inst.scroll(350)
        self._place_order()
        self._new_order()
        time.sleep(2)

    def _market_sell(self, order: StockOrder) -> None:
        self._set_trading_type(order)
        self._set_symbol(order.sym)
        # inherently sets the action type because it is selling all stocks for that symbol
        self._chrome_inst.find(By.XPATH, '//*[@id="mcaio-sellAllHandle"]').click()

        amount_elem = self._chrome_inst.find(
            By.XPATH, '//*[@id="ordernumber01inputqty-stepper-input"]'
        )
        self._chrome_inst.sendKeyboardInput(amount_elem, str(order.quantity))
        self._chrome_inst.scroll(500)  # FIXME: scroll so button in view
        time.sleep(1)
        self._review_order()
        self._chrome_inst.scroll(350)
        self._place_order()
        self._new_order()
        time.sleep(2)

    def _limit_buy(self, order: StockOrder) -> Any:
        return NotImplementedError

    def _limit_sell(self, order: StockOrder) -> Any:
        return NotImplementedError

    def login(self) -> None:
        time.sleep(1)
        self._chrome_inst.switchToFrame("lmsIframe")
        login_input_elem = self._chrome_inst.find(By.XPATH, '//*[@id="loginIdInput"]')
        self._chrome_inst.sendKeyboardInput(login_input_elem, SCHWAB_LOGIN)
        password_input_elem = self._chrome_inst.find(
            By.XPATH, '//*[@id="passwordInput"]'
        )
        self._chrome_inst.sendKeyboardInput(password_input_elem, SCHWAB_PASSWORD)
        login_button = self._chrome_inst.find(By.XPATH, '//*[@id="btnLogin"]')
        login_button.click()
        time.sleep(5)
        self._chrome_inst.resetFrame()
        self._chrome_inst.open("https://client.schwab.com/app/trade/tom/trade")
        time.sleep(1)

    def download_trade_data(self, date: str) -> None:
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

    def get_current_positions(self) -> tuple[list[StockOrder], list[OptionOrder]]:
        """
        used to automatically sell left over positions
        :return: list of (symbol, amount)
        """
        self._chrome_inst.open("https://client.schwab.com/app/accounts/positions/#/")
        positions: list[StockOrder] = []
        try:
            time.sleep(5)
            page_source = self._chrome_inst.get_page_source()
            dfs = pd.read_html(StringIO(page_source))
            df = dfs[0]
            df = df[["Symbol", "Quantity"]].drop(df.index[[-1, -2]])
            temp = df.to_numpy()
            positions = [StockOrder(x[0], float(x[1])) for x in temp]
        except Exception as e:
            print("Error getting current positions", e)
        self._chrome_inst.open("https://client.schwab.com/app/trade/tom/#/trade")
        time.sleep(3)
        return positions, []

    def buy_option(self, order: OptionOrder) -> None:
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

    def sell_option(self, order: OptionOrder) -> None:
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

    def _buy_call_option(self, order: OptionOrder) -> None:
        self._perform_action(order, ActionType.OPEN)

    def _sell_call_option(self, order: OptionOrder) -> None:
        self._perform_action(order, ActionType.CLOSE)

    def _buy_put_option(self, order: OptionOrder) -> None:
        self._perform_action(order, ActionType.OPEN)

    def _sell_put_option(self, order: OptionOrder) -> None:
        self._perform_action(order, ActionType.CLOSE)

    def _perform_action(self, order: OptionOrder, action: ActionType) -> None:
        self._set_symbol(order.sym)
        self._set_trading_type(order)
        self._set_action(action)
        self._enter_option_string(order)
        self._choose_order_type(order)
        self._review_order()
        self._place_order()
        self._new_order()

    def _place_order(self) -> None:
        time.sleep(1)
        place_order_btn = self._chrome_inst.find(
            By.XPATH, '//*[@id="mtt-place-button"]'
        )
        place_order_btn.click()

    def _set_symbol(self, sym: str) -> None:
        symbol_elem = self._chrome_inst.find(By.XPATH, '//*[@id="_txtSymbol"]')
        self._chrome_inst.sendKeyboardInput(symbol_elem, sym)
        symbol_elem.send_keys(Keys.RETURN * 2)
        time.sleep(2)  # wait for trade page to load again

    def _new_order(self) -> None:
        time.sleep(1)
        new_order_btn = self._chrome_inst.find(
            By.XPATH, '//*[@id="mcaio-footer"]/div/div/button[3]'
        )
        new_order_btn.click()

    def _review_order(self) -> None:
        review_order_btn = self._chrome_inst.find(
            By.XPATH, '//*[@id="mcaio-footer"]/div/div[2]/button[2]'
        )
        review_order_btn.click()  # wait for trade page to load again

    def _set_trading_type(self, order: Union[StockOrder, OptionOrder]) -> None:
        dropdown = self._chrome_inst.find(By.XPATH, '//button[@id="aiott-strategy"]')
        dropdown.click()
        if isinstance(order, StockOrder):
            self._chrome_inst.find(
                By.XPATH, '//*[@id="mcaio-level-1-item-tradeStrategyMenustock"]/ol/li'
            ).click()
        else:  # option trading
            path = None
            if order.option_type == OptionType.CALL:
                path = '//*[@id="mcaio-level-1-item-tradeStrategyoptions"]/ol[1]/li'
            else:
                path = '//*[@id="mcaio-level-1-item-tradeStrategyoptions"]/ol[2]/li'
            self._chrome_inst.find(By.XPATH, path).click()
        time.sleep(0.5)

    def _set_action(self, action: ActionType) -> None:
        element = self._chrome_inst.find(By.XPATH, '//*[@id="_action"]')
        dropdown = Select(element)
        if action == ActionType.OPEN:
            dropdown.select_by_visible_text("Buy to open")
        elif action == ActionType.CLOSE:
            dropdown.select_by_visible_text("Sell to close")
        elif action == ActionType.BUY:
            dropdown.select_by_visible_text("Buy")
        elif action == ActionType.SELL:
            dropdown.select_by_visible_text("Sell")

    def _enter_option_string(self, order: OptionOrder) -> None:
        self._chrome_inst.find(By.XPATH, '//*[@id="_AutoGroup"]/button[2]').click()
        option = f"{order.sym.upper()} {order.formatted_expiration()} {order.strike} {order.option_type.value[0]}"
        option_elem = self._chrome_inst.find(
            By.XPATH, '//*[@id="_ManualGroup"]/div/div/input'
        )
        self._chrome_inst.sendKeyboardInput(option_elem, option)

    def _choose_order_type(self, order: OptionOrder) -> None:
        element = self._chrome_inst.find(
            By.XPATH, '//*[@id="mcaio-orderType-container"]/div/div/div/select'
        )
        dropdown = Select(element)
        if order.order_type == OrderType.MARKET:
            dropdown.select_by_visible_text("Market")
        else:
            dropdown.select_by_visible_text("Limit")


if __name__ == "__main__":
    s = Schwab(Path("temp.csv"), BrokerNames.SB, Path("temp_option.csv"))
    s.login()
    pass
