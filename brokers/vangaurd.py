import time
from brokers import VANGUARD_LOGIN, VANGUARD_PASSWORD
from utils.broker import Broker, OptionOrder, StockOrder
from utils.report.report import (
    ActionType,
    BrokerNames,
    OptionData,
    OptionType,
    OrderType,
    StockData,
)
from utils.selenium_helper import CustomChromeInstance
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By


class Vanguard(Broker):
    def __init__(self, report_file, broker_name: BrokerNames, option_report_file=None):
        super().__init__(report_file, broker_name, option_report_file)
        self._chrome_inst = CustomChromeInstance()
        self._chrome_inst.open(
            "https://personal.vanguard.com/us/TradeTicket?investmentType=OPTION"
        )

    def login(self):
        username_input = self._chrome_inst.find(By.XPATH, '//*[@id="USER"]')
        self._chrome_inst.sendKeyboardInput(username_input, VANGUARD_LOGIN)
        password_input = self._chrome_inst.find(By.XPATH, '//*[@id="PASSWORD-blocked"]')
        self._chrome_inst.sendKeyboardInput(password_input, VANGUARD_PASSWORD)
        login_btn = self._chrome_inst.find(
            By.XPATH, '//*[@id="username-password-submit-btn-1"]'
        )
        login_btn.click()
        time.sleep(1)

    def buy(self, order: StockOrder):
        return NotImplemented

    def sell(self, order: StockOrder):
        return NotImplemented

    def _market_buy(self, order: StockOrder):
        return NotImplemented

    def _market_sell(self, order: StockOrder):
        return NotImplemented

    def _limit_buy(self, order: StockOrder):
        return NotImplemented

    def _limit_sell(self, order: StockOrder):
        return NotImplemented

    def buy_option(self, order: OptionOrder):
        pass

    def sell_option(self, order: OptionOrder):
        pass

    def _get_stock_data(self, sym: str) -> StockData:
        pass

    def _get_option_data(self, order: OptionOrder) -> OptionData:
        pass

    def _buy_call_option(self, order: OptionOrder):
        self._set_option_type(order.option_type)

    def _sell_call_option(self, order: OptionOrder):
        pass

    def _buy_put_option(self, order: OptionOrder):
        pass

    def _sell_put_option(self, order: OptionOrder):
        pass

    def _set_option_type(self, option_type: OptionType):
        if option_type == OptionType.CALL:
            self._chrome_inst.find(
                By.XPATH, '//*[@id="baseForm:callRadioButton"]'
            ).click()
        else:
            self._chrome_inst.find(
                By.XPATH, '//*[@id="baseForm:putRadioButton"]'
            ).click()

    def _set_transaction_type(self):
        pass

    def get_current_positions(self) -> list[StockOrder]:
        return NotImplemented

    def _save_report(
        self,
        sym: str,
        action_type: ActionType,
        program_submitted,
        program_executed,
        pre_stock_data: StockData,
        post_stock_data: StockData,
        **kwargs
    ):
        pass

    def _save_option_report(
        self,
        order: OptionOrder,
        action_type: ActionType,
        program_submitted,
        program_executed,
        pre_stock_data: OptionData,
        post_stock_data: OptionData,
        **kwargs
    ):
        pass


if __name__ == "__main__":
    broker = Vanguard("temp.csv", BrokerNames.VD)
    broker.login()
