from pathlib import Path
import time
from typing import Any, Optional, Union
from brokers import VANGUARD_LOGIN, VANGUARD_PASSWORD
from utils.broker import Broker, OptionOrder, StockOrder
from utils.market_data import MarketData
from utils.report.report import (
    NULL_STOCK_DATA,
    ActionType,
    BrokerNames,
    OptionData,
    OptionReportEntry,
    OptionType,
    OrderType,
    StockData,
)
from utils.selenium_helper import CustomChromeInstance
from selenium.webdriver.common.by import By


class Vanguard(Broker):
    def __init__(
        self,
        report_file: Path,
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        super().__init__(report_file, broker_name, option_report_file)
        self._chrome_inst = CustomChromeInstance(undetected=True)
        self._chrome_inst.open(
            "https://personal.vanguard.com/us/TradeTicket?investmentType=OPTION"
        )

    def login(self) -> None:
        username_input = self._chrome_inst.find(By.XPATH, '//*[@id="USER"]')
        self._chrome_inst.sendKeyboardInput(username_input, VANGUARD_LOGIN)
        time.sleep(2)
        password_input = self._chrome_inst.find(By.XPATH, '//*[@id="PASSWORD-blocked"]')
        self._chrome_inst.sendKeyboardInput(password_input, VANGUARD_PASSWORD)
        time.sleep(2)
        login_btn = self._chrome_inst.find(
            By.XPATH, '//*[@id="username-password-submit-btn-1"]'
        )
        login_btn.click()
        input("Done logging in (VD)? (press enter to continue)")

    def buy(self, order: StockOrder) -> Any:
        return NotImplemented

    def sell(self, order: StockOrder) -> Any:
        return NotImplemented

    def _market_buy(self, order: StockOrder) -> Any:
        return NotImplemented

    def _market_sell(self, order: StockOrder) -> Any:
        return NotImplemented

    def _limit_buy(self, order: StockOrder) -> Any:
        return NotImplemented

    def _limit_sell(self, order: StockOrder) -> Any:
        return NotImplemented

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

    def _get_stock_data(self, sym: str) -> StockData:
        return NULL_STOCK_DATA

    def _get_option_data(self, order: OptionOrder) -> OptionData:
        return MarketData.get_option_data(order)

    def _buy_call_option(self, order: OptionOrder) -> None:
        self._perform_option_buy_order(order, ActionType.OPEN)

    def _sell_call_option(self, order: OptionOrder) -> None:
        self._perform_option_sell_order(order, ActionType.CLOSE)

    def _buy_put_option(self, order: OptionOrder) -> None:
        self._perform_option_buy_order(order, ActionType.OPEN)

    def _sell_put_option(self, order: OptionOrder) -> None:
        self._perform_option_sell_order(order, ActionType.CLOSE)

    def _perform_option_buy_order(self, order: OptionOrder, action: ActionType) -> None:
        self._set_option_type(order.option_type)
        self._set_transaction_type(action)
        self._set_symbol(order.sym)
        self._set_expiration(order.expiration)
        self._set_strike(order.strike)
        self._set_quantity(order.quantity)
        self._set_price(order, action)
        self._set_day()
        self._place_order()

    def _perform_option_sell_order(
        self, order: OptionOrder, action: ActionType
    ) -> None:
        self._set_option_type(order.option_type)
        self._set_transaction_type(action)
        time.sleep(2)
        self._find_option_to_sell(order)
        self._set_quantity(order.quantity)
        self._set_price(order, action)
        self._set_day()
        self._place_order(action)

    def _set_option_type(self, option_type: OptionType) -> None:
        if option_type == OptionType.CALL:
            self._chrome_inst.find(
                By.XPATH, '//*[@id="baseForm:callRadioButton"]'
            ).click()
        else:
            self._chrome_inst.find(
                By.XPATH, '//*[@id="baseForm:putRadioButton"]'
            ).click()
        time.sleep(2)

    def _set_transaction_type(self, action: ActionType) -> None:
        self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:transactionTypeSelectOne_main"]'
        ).click()
        if action == ActionType.OPEN:
            self._chrome_inst.find(
                By.XPATH, '//*[@id="baseForm:transactionTypeSelectOne:1"]'
            ).click()
        else:
            self._chrome_inst.find(
                By.XPATH, '//*[@id="baseForm:transactionTypeSelectOne:2"]'
            ).click()

    def _set_symbol(self, sym: str) -> None:
        symbol_input = self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:investmentTextField"]'
        )
        self._chrome_inst.sendKeyboardInput(symbol_input, sym)
        time.sleep(2)

    def _convert_date(self, date: str) -> str:
        month, day, year = date.split("/")
        return f"{year}-{month}-{day}"

    def _set_expiration(self, expiration: str) -> None:

        self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:expirationDateSelectOne_textCont"]'
        ).click()
        idx = 1
        while idx < 15:
            try:
                expiration_input = self._chrome_inst.find(
                    By.XPATH, f'//*[@id="baseForm:expirationDateSelectOne:{idx}"]'
                )
                if self._convert_date(expiration_input.text) == expiration:
                    expiration_input.click()
                    break
            except:
                pass
            idx += 1
        time.sleep(1)

    def _set_strike(self, strike: str) -> None:
        self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:strikePriceSelectOne_textCont"]'
        ).click()

        idx = 1
        formatted_strike = "{0:,.2f}".format(float(strike))
        while idx < 1000:
            try:
                strike_input = self._chrome_inst.find(
                    By.XPATH, f'//*[@id="baseForm:strikePriceSelectOne:{idx}"]'
                )
                if strike_input.text[1:] == formatted_strike:
                    strike_input.click()
                    break
            except:
                pass
            idx += 1
        time.sleep(1)

    def _set_quantity(self, quantity: int) -> None:
        elem = self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:shareQuantityTextField"]'
        )
        self._chrome_inst.sendKeyboardInput(elem, str(quantity))

    def _set_price(self, order: OptionOrder, action: ActionType) -> None:
        price_input = self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:limitPriceTextField"]'
        )
        if action == ActionType.OPEN:
            price = float(self._get_option_data(order).ask) * 1.03
        else:
            price = float(self._get_option_data(order).bid) * 0.97
            if price < 0.01:
                price = 0.01
        price = self._handle_option_tick_size(action, price)
        self._chrome_inst.sendKeyboardInput(price_input, str(round(price, 2)))
        time.sleep(1)

    def _set_day(self) -> None:
        self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:durationTypeSelectOne_textCont"]'
        ).click()

        self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:durationTypeSelectOne:1"]'
        ).click()

    def _place_order(self, action: ActionType = ActionType.BUY) -> None:
        self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:reviewButtonInput"]'
        ).click()
        time.sleep(2)
        if action == ActionType.CLOSE:
            self._chrome_inst.find(
                By.XPATH, '//*[@id="orderCaptureWarningLayerForm:yesButtonInput"]'
            ).click()
        time.sleep(2)
        self._chrome_inst.find(
            By.XPATH, '//*[@id="baseForm:submitButtonInput"]'
        ).click()
        time.sleep(1)
        self._chrome_inst.open(
            "https://personal.vanguard.com/us/TradeTicket?accountId=258586230212504&investmentType=OPTION"
        )

    def _find_option_to_sell(self, order: OptionOrder) -> None:
        def check_option(option_text: str) -> bool:
            parts = option_text.split(" ")
            if parts[0] != order.sym:
                return False
            if self._convert_date(parts[1]) != order.expiration:
                return False
            if parts[2] != order.option_type.value[0].upper():
                return False
            if float(parts[3][1:]) != float(order.strike):
                return False
            return True

        idx = 2
        while idx < 10:
            try:
                option_text = self._chrome_inst.find(
                    By.XPATH,
                    f'//*[@id="optionsSellToCloseHoldingsForm:optionsSellToCloseTabletbody0"]/tr[{idx}]/td[2]',
                )

                if check_option(option_text.text):
                    self._chrome_inst.find(
                        By.XPATH,
                        f'//*[@id="optionsSellToCloseHoldingsForm:optionsSellToCloseTabletbody0"]/tr[{idx}]/td[1]/table/tbody/tr/td/label/input',
                    ).click()
                    self._chrome_inst.find(
                        By.XPATH,
                        '//*[@id="optionsSellToCloseHoldingsForm:continueButtonInput"]',
                    ).click()
                    time.sleep(2)
            except:
                pass
            idx += 1

    def get_current_positions(self) -> tuple[list[StockOrder], list[OptionOrder]]:
        return [], []

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
        pass

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
                order.quantity,
                None,
                pre_stock_data,
                post_stock_data,
                OrderType.LIMIT,
                None,
                None,
                None,
                BrokerNames.VD,
            )
        )
        self._save_option_report_to_file()

    def download_trade_data(self, dates: list[str]) -> None:
        # TODO: doesn't completely work
        self._chrome_inst.open("https://confirmations.web.vanguard.com/")
        input("Waiting to set confirmation type to monetary")
        idx = 1
        while True:
            try:
                date = self._chrome_inst.find(
                    By.XPATH, f'//*[@id="confirms-table"]/tbody/tr[{idx}]/td[1]'
                ).text
                print(f"Downloading {date}")
                download = self._chrome_inst.find(
                    By.XPATH, f'//*[@id="download-icon-{idx-1}"]'
                )
                download.click()
                time.sleep(2)
                idx += 1
            except:
                break


if __name__ == "__main__":
    vd = Vanguard(Path("temp.csv"), BrokerNames.VD, Path("temp_option.csv"))
    vd.login()
    vd.download_trade_data([])
