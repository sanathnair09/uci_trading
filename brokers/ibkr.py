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
from selenium.webdriver.remote.webelement import WebElement

from brokers import IBKR_LOGIN, IBKR_PASSWORD
from utils.broker import Broker, StockOrder, OptionOrder
from utils.market_data import MarketData
from utils.report.report import (
    NULL_STOCK_DATA,
    BrokerNames,
    OptionData,
    OrderType,
    ActionType,
    ReportEntry,
    StockData,
)
from utils.selenium_helper import CustomChromeInstance
from utils.util import repeat


class IBKR(Broker):
    """
    IBKR IS VERY SCARY
    """

    def __init__(
        self,
        report_file: Path,
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        super().__init__(report_file, broker_name, option_report_file)
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open("https://ndcdyn.interactivebrokers.com/sso/Login")

    def login(self) -> None:
        username_elem = self._chrome_inst.find(
            By.XPATH,
            "/html/body/section[1]/div/div/div[2]/div[2]/form[2]/div[1]/fieldset[1]/div/input",
        )
        self._chrome_inst.sendKeyboardInput(username_elem, IBKR_LOGIN)

        password_elem = self._chrome_inst.find(
            By.XPATH,
            "/html/body/section[1]/div/div/div[2]/div[2]/form[2]/div[1]/fieldset[2]/div/input",
        )
        self._chrome_inst.sendKeyboardInput(password_elem, IBKR_PASSWORD)

        login_btn = self._chrome_inst.find(
            By.XPATH,
            "/html/body/section[1]/div/div/div[2]/div[2]/form[2]/div[2]/div[1]/button",
        )
        login_btn.click()

        print("Waiting for 2fa...", end="")
        input()

        trade_nav = self._chrome_inst.find(
            By.XPATH,
            "/html/body/div[1]/header/section/div/div/div[3]/div[3]/div/button",
        )
        trade_nav.click()

        time.sleep(2)  # wait for the trade window to appear on screen

        self.fix_permission()

    @repeat()
    def fix_permission(self) -> None:
        try:
            login_with_trading = self._chrome_inst.find(
                By.XPATH, "/html/body/div[4]/div/div[2]/div/div/div[1]/button"
            )
            login_with_trading.click()
        except:
            pass

    def _get_stock_data(self, sym: str) -> StockData:
        return NULL_STOCK_DATA

    def buy(self, order: StockOrder) -> None:
        pre_stock_data = MarketData.get_stock_data(order.sym)
        program_submitted = self._get_current_time()

        ### BUY ###
        if order.order_type == OrderType.MARKET:
            self._market_buy(order)
        else:
            self._limit_buy(order)

        program_executed = self._get_current_time()
        post_stock_data = MarketData.get_stock_data(order.sym)

        self._save_report(
            order.sym,
            ActionType.BUY,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
            quantity=order.quantity,
        )

    def sell(self, order: StockOrder) -> None:
        pre_stock_data = MarketData.get_stock_data(order.sym)
        program_submitted = self._get_current_time()

        if order.order_type == OrderType.MARKET:
            self._market_sell(order)
        else:
            self._limit_sell(order)

        program_executed = self._get_current_time()
        post_stock_data = MarketData.get_stock_data(order.sym)

        self._save_report(
            order.sym,
            ActionType.SELL,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
            quantity=order.quantity,
        )

    def buy_option(self, order: OptionOrder) -> Any:
        return NotImplementedError

    def sell_option(self, order: OptionOrder) -> Any:
        return NotImplementedError

    def _market_buy(self, order: StockOrder) -> None:
        try:
            self._choose_stock(order.sym)
            self._set_amount(order.quantity)
            self._choose_order_type(OrderType.MARKET, ActionType.BUY)
            self._validate_order(order.sym, ActionType.BUY)
        except Exception as e:
            raise e

    def _market_sell(self, order: StockOrder) -> None:
        try:
            self._choose_stock(order.sym)
            self._set_sell()
            self._set_amount(order.quantity)
            self._choose_order_type(OrderType.MARKET, ActionType.SELL)
            self._validate_order(order.sym, ActionType.SELL)
        except Exception as e:
            raise e

    def _limit_buy(self, order: StockOrder) -> Any:
        return NotImplementedError

    def _limit_sell(self, order: StockOrder) -> Any:
        return NotImplementedError

    def _test_variation(self, path: str, *args: int) -> WebElement:
        """
        place the numbers in args in probability of expecting it (i.e. if 5 is more likely than 4 do 5, 4)
        :param path:
        :param args:
        :return:
        """
        for arg in args:
            test_path = path.replace("{f}", str(arg))
            try:
                res = self._chrome_inst.waitForElementToLoad(By.XPATH, test_path, 5)
                return res
            except:
                pass
        raise NoSuchElementException()

    def _choose_stock(self, sym: str) -> None:
        sym_input = self._test_variation(
            "/html/body/div[{f}]/div/div[2]/div[1]/div[1]/div/div/form/div/span/span/input",
            5,
            6,
            7,
            4,
        )
        for _ in range(6):  # largest stock name
            sym_input.send_keys(Keys.BACKSPACE)
        self._chrome_inst.sendKeyboardInput(sym_input, sym)
        sym_input.send_keys(Keys.RETURN)
        time.sleep(1)

        try:
            select_stock = self._test_variation(
                "/html/body/div[{f}]/div/div[2]/div[1]/div[1]/div/div/form/div/div[1]/ul[1]/li/ul/li[1]/div/a",
                5,
                6,
                7,
                4,
            )
            select_stock.click()
            time.sleep(1)
        except NoSuchElementException as _:
            pass  # some stocks don't have other choices like options etc

        time.sleep(1)

    def _set_sell(self) -> None:
        sell_tab = self._chrome_inst.find(By.XPATH, '//*[@id="sellTab"]')
        sell_tab.click()
        time.sleep(1)

    def _set_amount(self, amount: float) -> None:
        quantity_elem = self._test_variation(
            "/html/body/div[{f}]/div/div[3]/div[2]/div/div[2]/div[1]/form/div[2]/div/div[1]/div/div[1]/span/span/input",
            5,
            6,
            7,
            4,
        )
        if quantity_elem:
            # to remove the default 100 that is in the shares field
            quantity_elem.clear()
            quantity_elem.send_keys(Keys.BACKSPACE)
            quantity_elem.send_keys(Keys.BACKSPACE)
            quantity_elem.send_keys(Keys.BACKSPACE)
            self._chrome_inst.sendKeyboardInput(quantity_elem, str(amount))

        time.sleep(1)

    def _choose_order_type(
        self, order_type: OrderType, action_type: ActionType
    ) -> None:
        if action_type == ActionType.BUY:
            dropdown = self._test_variation(
                "/html/body/div[{f}]/div/div[3]/div[2]/div/div[2]/div[1]/form/div[2]/div/div[3]/div[1]/span/span",
                5,
                6,
                7,
                4,
            )
        else:
            dropdown = self._chrome_inst.find(
                By.XPATH,
                '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[1]/form/div[2]/div/div[2]/div[1]/span',
            )
        dropdown.click()
        if order_type == OrderType.MARKET:
            self._chrome_inst.sendKeys(Keys.DOWN)
            self._chrome_inst.sendKeys(Keys.DOWN)
            self._chrome_inst.sendKeys(Keys.RETURN)
        # limit is default

    def _go_back(self, action_type: ActionType) -> None:
        if action_type == ActionType.BUY:
            back_btn = self._chrome_inst.find(
                By.XPATH,
                '//*[@id="orderTicketBuyTabPanel"]/div/div[2]/div[2]/div[2]/div/button[1]',
            )
        else:
            back_btn = self._chrome_inst.find(
                By.XPATH,
                '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[2]/div[2]/div/button[1]',
            )
        text = back_btn.text
        if text == "Back":
            back_btn.click()

    def _validate_order(self, sym: str, action_type: ActionType) -> None:
        preview_btn = self._chrome_inst.find(By.XPATH, '//*[@id="cp-btn-preview"]')
        preview_btn.click()
        time.sleep(2)

        try:
            if action_type == ActionType.BUY:
                total_text = self._chrome_inst.find(
                    By.XPATH,
                    '//*[@id="orderTicketBuyTabPanel"]/div/div[2]/div[1]/div/div[1]/div/table/tr[5]/td[2]',
                ).text
                price = float(total_text[:-4].replace(",", ""))
                logger.info(f"IB - {sym} = {total_text}")

                if price <= self.THRESHOLD:
                    place_order = self._chrome_inst.find(
                        By.XPATH,
                        '//*[@id="orderTicketBuyTabPanel"]/div/div[2]/div[2]/div[2]/div/button[2]',
                    )
                    place_order.click()
                    time.sleep(1)
                    new_order = self._chrome_inst.find(
                        By.XPATH,
                        '//*[@id="orderTicketBuyTabPanel"]/div/div[2]/div[1]/div/div[4]/button[2]',
                    )
                    new_order.click()
                else:
                    self._go_back(action_type)

                    logger.error(f"Buying more than threshold")
            else:  # SELL
                post_trade_positions = self._chrome_inst.find(
                    By.XPATH,
                    '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[1]/div/div[2]/div/table/tr[2]/td[4]',
                )
                position_text = post_trade_positions.text
                if "-" in position_text:
                    self._go_back(action_type)

                    logger.error(
                        f"Selling more than what is owned. Post-trade position: {position_text}"
                    )
                else:
                    place_order = self._chrome_inst.find(
                        By.XPATH,
                        '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[2]/div[2]/div/button[2]',
                    )
                    place_order.click()
                    time.sleep(2)
                    new_order = self._chrome_inst.find(
                        By.XPATH,
                        '//*[@id="orderTicketSellTabPanel"]/div/div[2]/div[1]/div/div[4]/button[2]',
                    )
                    new_order.click()
        except Exception as e:
            logger.error(f"Error completing IF action for {sym}")
            self._go_back(action_type)

    def _get_option_data(self, order: OptionOrder) -> Any:
        return NotImplementedError

    def _buy_call_option(self, order: OptionOrder) -> Any:
        return NotImplementedError

    def _sell_call_option(self, order: OptionOrder) -> Any:
        return NotImplementedError

    def _buy_put_option(self, order: OptionOrder) -> Any:
        return NotImplementedError

    def _sell_put_option(self, order: OptionOrder) -> Any:
        return NotImplementedError

    def get_current_positions(self) -> tuple[list[StockOrder], list[OptionOrder]]:
        self._chrome_inst.open(
            "https://portal.interactivebrokers.com/portal/?action=ACCT_MGMT_MAIN&loginType=1&clt=0#/portfolio"
        )
        time.sleep(5)
        positions: list[StockOrder] = []
        try:
            page_source = self._chrome_inst.get_page_source()
            dfs = pd.read_html(StringIO(page_source))
            df = dfs[0]
            temp = df[["Instrument", "Position"]].to_numpy()
            positions = [
                StockOrder(sym if "●" not in sym else sym[1:], float(amount))
                for sym, amount in temp
            ]
        except Exception as e:
            print(e)
        return positions, []

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
                BrokerNames.IF,
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
    ) -> Any:
        return NotImplementedError


if __name__ == "__main__":
    a = IBKR(Path("temp.csv"), BrokerNames.IF)
    a.login()
    pass
