from pathlib import Path
import time
from datetime import datetime
from io import StringIO
from typing import Any, Optional, Union, cast
from collections import namedtuple


from numpy import rint
import pandas as pd
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
import math
# import datetime

import requests
import json

import asyncio
from ib_async import IB, Stock, ContractDetails, ExecutionFilter
from ib_async.contract import Option
from ib_async.order import MarketOrder, LimitOrder

# import robin_stocks.robinhood as rh

from brokers import BASE_PATH, IBKR_LOGIN, IBKR_PASSWORD
from utils.broker import Broker, StockOrder, OptionOrder
# from utils.market_data import MarketData
from utils.report.report import (
    NULL_STOCK_DATA,
    BrokerNames,
    OptionType,
    OptionData,
    OptionReportEntry,
    OrderType,
    ActionType,
    ReportEntry,
    StockData,
    TwentyFourReportEntry,
)
from utils.selenium_helper import CustomChromeInstance
from utils.util import repeat
from zoneinfo import ZoneInfo

class BuyOrderCancelledException(Exception):
    def __init__(self, message):
        super().__init__(message)  # Pass message to the base Exception class

class SellOrderCancelledException(Exception):
    def __init__(self, message):
        super().__init__(message)  # Pass message to the base Exception class

class IBKR(Broker):
    """
    IBKR IS VERY SCARY - DAMN!
    """

    def __init__(
        self,
        report_file: Path,
        broker_name: BrokerNames,
        option_report_file: Optional[Path] = None,
    ):
        super().__init__(report_file, broker_name, option_report_file)
        self.ib = IB()

        # self.robinhood = Robinhood(report_file, BrokerNames.RH, option_report_file)
        # self.robinhood.login()

        self.executions_length = 1
        self.open_buy_orders = dict()
        self.open_sell_orders = dict()

        
        # self._chrome_inst = CustomChromeInstance()
        # self._chrome_inst.open("https://ndcdyn.interactivebrokers.com/sso/Login")

    def login(self) -> None:
        self.ib.connect('127.0.0.1', port=7496, clientId=1)   # FOR NORMAL TRADING
        # self.ib.connect('127.0.0.1', port=7497, clientId=1)     # FOR PAPER TRADING
        if self.ib.isConnected():
            print("Successfully connected to TWS.")
            pass
        else:
            print("Failed to connect to TWS.")
        # asyncio.run(self._async_connect())
        
    def disconnect(self):
        # Use asyncio.run() to disconnect synchronously
        # asyncio.run(self._async_disconnect())
        self.ib.disconnect()


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
        # pre_stock_data = MarketData.get_stock_data(order.sym)
        # program_submitted = self._get_current_time()

        # ### BUY ###
        # if order.order_type == OrderType.MARKET:
        #     self._market_buy(order)
        # else:
        #     self._limit_buy(order)

        # program_executed = self._get_current_time()
        # post_stock_data = MarketData.get_stock_data(order.sym)
        
        # self._save_report(
        #     order.sym,
        #     ActionType.BUY,
        #     program_executed,
        #     program_submitted,
        #     pre_stock_data,
        #     post_stock_data,
        #     quantity=order.quantity,
        # )
        pass

    def sell(self, order: StockOrder) -> None:
        # pre_stock_data = MarketData.get_stock_data(order.sym)
        # program_submitted = self._get_current_time()

        # if order.order_type == OrderType.MARKET:
        #     self._market_sell(order)
        # else:
        #     self._limit_sell(order)

        # program_executed = self._get_current_time()
        # post_stock_data = MarketData.get_stock_data(order.sym)

        # self._save_report(
        #     order.sym,
        #     ActionType.SELL,
        #     program_executed,
        #     program_submitted,
        #     pre_stock_data,
        #     post_stock_data,
        #     quantity=order.quantity,
        # )
        pass

    def buy_option(self, order: OptionOrder) -> Any:
        '''
        IMPLEMENT THIS BAD BOY
        '''
        ### PRE BUY INFO ###
        pre_stock_data = self._get_option_data(order)       # needs to be implemented
        program_submitted = self._get_current_time()

        ### BUY OPTION ###
        if order.option_type == OptionType.CALL:
            self._buy_call_option(order)
        else:
            # not implemented yet
            self._buy_put_option(order)
        logger.info("Bought IBKR option")
        ### POST BUY INFO ###
        program_executed = self._get_current_time()
        post_stock_data = self._get_option_data(order)

        ### SAVE REPORT ### 
        self._save_option_report(
            order,
            ActionType.BUY,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
            orderID=None,           # adding in order id in save option report function
        )
    
    def _buy_call_option(self, order: OptionOrder) -> Any:
        expiration_date = order.expiration.replace('-', '')


        contract = Option(
            symbol=order.sym,
            lastTradeDateOrContractMonth=expiration_date,
            strike=order.strike,
            right='CALL',  
            exchange='SMART',  # Use SMART for automatic best execution

            # may not need these two
            # multiplier='',    
            # currency='USD',        
        )

        order = MarketOrder('BUY', order.quantity)
        trade = self.ib.placeOrder(contract, order)
        

    
    def _buy_put_option(self, order: OptionOrder) -> Any:
        return NotImplementedError



    def sell_option(self, order: OptionOrder) -> Any:
        '''
        IMPLEMENT THIS BAD BOY
        '''
        ### PRE SELL INFO ###
        pre_stock_data = self._get_option_data(order)
        program_submitted = self._get_current_time()
 
        ### SELL ###
        if order.option_type == OptionType.CALL:
            # orderID = self._sell_call_option(order)
            self._sell_call_option(order)
        else:
            # not implemented
            orderID = self._sell_put_option(order)
        logger.info("Sold IBKR option")

        ### POST BUY INFO ###
        program_executed = self._get_current_time()
        post_stock_data = self._get_option_data(order)

        self._save_option_report(
            order,
            ActionType.SELL,
            program_executed,
            program_submitted,
            pre_stock_data,
            post_stock_data,
            orderID=None,
        )
    
    def _sell_call_option(self, order: OptionOrder) -> Any:
        expiration_date = order.expiration.replace('-', '')

        contract = Option(
            symbol=order.sym,
            lastTradeDateOrContractMonth=expiration_date,
            strike=order.strike,
            right='CALL',  
            exchange='SMART',  # Use SMART for automatic best execution

            # may not need these two
            # multiplier='',      # ASK PROFESSOR WHAT MULITPLIER WOULD BE
            # currency='USD',        
        )

        order = MarketOrder('SELL', order.quantity)

        ### PLACE TRADE ###
        trade = self.ib.placeOrder(contract, order)

        # What should i return?
        return

    def _sell_put_option(self, order: OptionOrder) -> Any:
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
        expiration_date = order.expiration.replace('-', '')
        contract = Option(
            symbol=order.sym,
            lastTradeDateOrContractMonth=expiration_date,
            strike=order.strike,
            right='CALL',  
            exchange='SMART',  # Use SMART for automatic best execution

            # may not need these two
            # multiplier='',      # ASK PROFESSOR WHAT MULITPLIER WOULD BE
            # currency='USD',        
        )

        ticker = self.ib.reqMktData(contract, genericTickList="100")

        total_time = 0
        while not ticker.modelGreeks:
            if total_time == 5:
                print("Unable to get IBKR ticker data")
                break
            self.ib.sleep(1)
            total_time += 1
   
        
        # need to get smth with all of this:
        return OptionData(
            ticker.ask,           
            ticker.bid,           
            ticker.contract.lastTradeDateOrContractMonth,          #think this is it - verify what it is
            None, # possibilities[keys][key][0]["totalVolume"],    # don't have it
            ticker.modelGreeks.impliedVol,   
            ticker.modelGreeks.delta,         
            ticker.modelGreeks.theta,         
            ticker.modelGreeks.gamma,         
            ticker.modelGreeks.vega,          
            None, # possibilities[keys][key][0]["rho"],           # don't have it
            round(ticker.modelGreeks.undPrice, 4),     #think we have it - verify what it is
            None, # possibilities[keys][key][0]["inTheMoney"],    # don't have it
        )

    def _get_quote_date(self, order: OptionOrder) -> Any:
        expiration_date = order.expiration.replace('-', '')
        contract = Option(
            symbol=order.sym,
            lastTradeDateOrContractMonth=expiration_date,
            strike=order.strike,
            right='CALL',  
            exchange='SMART',  # Use SMART for automatic best execution

            # may not need these two
            # multiplier='',      # ASK PROFESSOR WHAT MULITPLIER WOULD BE
            # currency='USD',        
        )
        # contract = Stock('AAPL', 'NASDAQ', 'USD')

        # NORMAL MARKET DATA:
        ticker = self.ib.reqMktData(contract, genericTickList="100")
        # self.ib.sleep(2)
        while not ticker.modelGreeks:
            self.ib.sleep(1)
        print(ticker)
        print("GREEKS:")
        print(ticker.modelGreeks)
        print(f"ASK: {ticker.ask}")
        print(f"BID: {ticker.bid}")
        print(f"LAST: {ticker.contract.lastTradeDateOrContractMonth}")
        print(f"TOTAL VOLUME: ")
        print(f"VOLATILITY: {ticker.modelGreeks.impliedVol} ")
        print(f"DELTA: {ticker.modelGreeks.delta}")
        print(f"THETA: {ticker.modelGreeks.theta}")
        print(f"GAMMA: {ticker.modelGreeks.gamma}")
        print(f"VEGA: {ticker.modelGreeks.vega}")
        print(f"RHO: ")
        print(f"UNDERLYING PRICE: {round(ticker.modelGreeks.undPrice, 4)}")
        print(F"IN THE MONEY: ")

        # GET PRICE, BROKER EXECUTED TIME, ORDER ID
        # executions = self.ib.executions()
        # print(f"Executions: {executions}")
        # print(f"Most recent execution: {executions[-1]}")
        # most_recent_execution = executions[-1]
        # print(f"Price: {most_recent_execution.price}")
        # print(f"Execution Time: {most_recent_execution.time}")
        # print(f"Order ID: {most_recent_execution.orderId}")


    def get_current_positions(self):
        positions = self.ib.positions()
        self.ib.sleep(4)
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
        executions = self.ib.executions()
        self.ib.sleep(4)
        price, order_time, order_id = None, None, None
        try:
            
            most_recent_execution = executions[-1]
            print(f"Price: {most_recent_execution.price}")
            print(f"Execution Time: {most_recent_execution.time.strftime('%I:%M:%S:%f')[:12]}")
            print(f"Order ID: {most_recent_execution.orderId}")
            price = most_recent_execution.price
            order_time = most_recent_execution.time.strftime('%I:%M:%S:%f')[:12]
            order_id = most_recent_execution.orderId
        except Exception as e:
            logger.info(f"Error with most recent execution data: {e}")
            
        logger.info("Adding IBKR Option to report")
        self._add_option_report_to_file(
            OptionReportEntry(
                program_submitted,
                program_executed,
                order_time,           # GET BROKER EXECUTED TIME
                order.sym,
                order.strike,
                order.option_type,
                order.expiration,
                action_type,
                order.quantity,
                price,           # GET PRICE OF STOCK
                pre_stock_data,
                post_stock_data,
                OrderType.MARKET,
                None,               # venue (optional)
                order_id,               # order_id (optional)
                None,               # activity_id (optional)
                BrokerNames.IF
            )
        )

        logger.info("Saving IBKR Option to report")
        self._save_option_report_to_file()
    

# ----------------------------------------------------------------------------------------------------------------------------
# 24 Hour Trading Methods




    def buy_and_sell_immediately(self, symbol):

        # OLD CODE WITH LOOP TO SELL LATER
        # try:
        #     ask_price = self.buy_limit(symbol)
        #     buy_program_submitted = datetime.now().strftime("%I:%M:%S %p")
        #     self.open_buy_orders[symbol] = (buy_program_submitted, ask_price)
        #     # print(self.open_buy_orders)
        #     logger.info(f"Bought {symbol} on IBKR")
        # except Exception as e:
        #     logger.error("Exception Caught on IBKR:")
        #     logger.error(e)

        pacific_tz = ZoneInfo("US/Pacific")
        now = datetime.now(pacific_tz).time()
        start_time = datetime.strptime("01:00", "%H:%M").time()
        end_time = datetime.strptime("07:10", "%H:%M").time()
        
        # IF TIME IS NOT BETWEEN 1:00 AM and 7:10 AM, DO NOT TRADE
        if not start_time <= now <= end_time:
            return

        try:
            buy_program_submitted = datetime.now().strftime("%I:%M:%S %p")
            ask_price = self.get_ask_price(symbol)
            buy_limit_price = self.buy_limit(symbol)

            if symbol not in self.get_open_positions():
                raise BuyOrderCancelledException("Buy order did not go through!")
            
            logger.info(f"Bought {symbol} on IBKR")

            sell_program_submitted = datetime.now().strftime("%I:%M:%S %p")
            bid_price = self.get_bid_price(symbol)
            sell_limit_price = self.sell_limit(symbol)

            # if order IS in open orders, do we raise some kind of exception?
            if symbol in self.get_open_positions():
                raise SellOrderCancelledException("Sell order did not go through!")

            logger.info(f"Sold {symbol} on IBKR")

        except BuyOrderCancelledException as e:  
            logger.info("Exception Caught on IBKR!")
            print(e)
            ask_price = self.get_ask_price(symbol)
            bid_price = self.get_bid_price(symbol)
            self.add_rejected_order_to_report(symbol, buy_program_submitted, ask_price, bid_price)
            return
        
        except SellOrderCancelledException as e:
            logger.info("Exception Caught on IBKR!")
            print(e)
            bid_price = self.get_bid_price(symbol)
            self.add_filled_buy_order_and_rejected_sell_order_to_report(symbol, buy_program_submitted, sell_program_submitted, ask_price, bid_price, buy_limit_price)
            return

        try:
            self.add_to_24_hour_report(symbol, buy_program_submitted, sell_program_submitted, ask_price, bid_price, buy_limit_price, sell_limit_price)
        except Exception as e:
            print(e)
            logger.info("Exception Caught while adding to report on IB")
    
# =================================================================================================================

    def buy_limit(self, symbol):

        # IF TIME IS EXTENDED HOURS:

        if self.get_correct_market_flag() == "extended_hours" or self.get_correct_market_flag() == "regular_hours":
            contract = Stock(
                symbol=symbol,
                exchange='SMART',  # Use SMART for automatic best execution
                currency='USD'
            )

            # Get limit price from robinhood
            # ask_price = self.robinhood.get_ask_price(symbol)
            ask_price = self.get_ask_price(symbol)
            limit_price = round(ask_price * 1.01, 2)
            # limit_price = round(ask_price * 1.1, 2)


            # print(f"Limit Price: {limit_price}")

            # Create order
            order = LimitOrder(
                action='BUY', 
                totalQuantity=1, 
                lmtPrice=limit_price
            )
            order.tif = 'GTC'
            order.outsideRth = True
            # # Place order
            trade = self.ib.placeOrder(contract, order)
            # print(trade)
            # print("Bought Limit")
            return limit_price

       # FOR OVERNIGHT HOURS
        elif self.get_correct_market_flag() == "overnight_hours":
        
            contract = Stock(
                symbol=symbol,
                exchange='SMART', 
                currency='USD',
            )


            contracts = self.ib.qualifyContracts(contract)
            print(f"Qualified contracts: {contracts}")

            if not contracts:
                print("Contract qualification failed!")
                return None

            contract = contracts[0]
            print(f"ConId: {contract.conId}")  # Should be a real number, not 0



            # Get limit price
            ask_price = self.get_ask_price(symbol)
            limit_price = round(ask_price * 1.05, 2)
            order = LimitOrder(
                action='BUY', 
                totalQuantity=1.0, 
                lmtPrice=limit_price
            )


            order.outsideRth = True
            order.transmit = True
            order.tif = 'GTC'
            # Place order
            trade = self.ib.placeOrder(contract, order)

            # self.ib.waitOnUpdate(timeout=5)

            # print(f"Status: {trade.orderStatus.status}")
            # print(f"WhyHeld: {trade.orderStatus.whyHeld}")
            # print(f"Order ID: {trade.order.orderId}")
            # print(f"Status: {trade.orderStatus.status}")
            # print(f"WhyHeld: {trade.orderStatus.whyHeld}")  # This is key — shows rejection reason
            # print(f"Filled: {trade.orderStatus.filled}")
            # print(f"Remaining: {trade.orderStatus.remaining}")
            return limit_price

# =================================================================================================================

    def sell_limit(self, symbol):

        # FOR AFTER HOURS
        if self.get_correct_market_flag() == "extended_hours" or self.get_correct_market_flag() == "regular_hours":
            contract = Stock(
                symbol=symbol,
                exchange='SMART',  # Use SMART for automatic best execution
                currency='USD'
            )

            # Get limit price
            bid_price = self.get_bid_price(symbol)
            limit_price = round(bid_price * 0.98, 2)
            # limit_price = round(bid_price * 0.9, 2)

            
            # Create order
            order = LimitOrder(
                action='SELL', 
                totalQuantity=1, 
                lmtPrice=limit_price
            )
            order.tif = 'GTC'
            order.outsideRth = True
            
            # Place order
            trade = self.ib.placeOrder(contract, order)
            return limit_price


        # FOR OVERNIGHT HOURS
        elif self.get_correct_market_flag() == "overnight_hours":
            contract = Stock(
                symbol=symbol,
                exchange='OVERNIGHT', 
                currency='USD'
            )
            # contract = Stock(
            #     symbol=symbol,
            #     exchange='SMART', 
            #     currency='USD'
            # )

            # Get limit price
            bid_price = self.get_bid_price(symbol)
            limit_price = round(bid_price * 0.98, 2)
            # print(f"Limit Price: {limit_price}")

            # Create order
            order = LimitOrder(
                action='SELL', 
                totalQuantity=1, 
                lmtPrice=limit_price
            )
            order.outsideRth = True
            
            # Place order
            trade = self.ib.placeOrder(contract, order)
            order.transmit = True
            # order.tif = 'OND'
            # print("Sold Limit")
            return limit_price

# =================================================================================================================

    def add_to_24_hour_report(self, symbol, buy_program_submitted, sell_program_submitted, ask_price, bid_price, buy_limit_price, sell_limit_price):

        self.ib.sleep(3)

        # Create report entries
        buy_execution_filter = ExecutionFilter(symbol=symbol, side="BUY")
        buy_execution = self.ib.reqExecutions(execFilter=buy_execution_filter)[-1].execution
        buy_price = buy_execution.price
        buy_exection_time = buy_execution.time.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%I:%M:%S %p")
        buy_report_entry = self.create_24_hour_report_entry(buy_price, symbol, "BUY", buy_program_submitted, buy_exection_time, ask_price, bid_price, buy_limit_price)

        sell_execution_filter = ExecutionFilter(symbol=symbol, side="SELL")
        sell_execution = self.ib.reqExecutions(execFilter=sell_execution_filter)[-1].execution
        sell_price = sell_execution.price
        sell_execution_time = sell_execution.time.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%I:%M:%S %p")
        sell_report_entry = self.create_24_hour_report_entry(sell_price, symbol, "SELL", sell_program_submitted, sell_execution_time, ask_price, bid_price, sell_limit_price)

        # print("IBKR")
        # print(buy_price)
        # print(sell_price)

        # Calculate spread, add spread to entry
        spread_value =  round(float(buy_price) - float(sell_price), 2)
        buy_report_entry.spread = spread_value
        sell_report_entry.spread = spread_value

        # write to report file
        # logger.info("Writing to csv")
        logger.info(f"Added {symbol} to report for IB")

        date = datetime.now().strftime("%m_%d")
        report_file = BASE_PATH / f"reports/24_hour/24_report_{date}_2026.csv"
        with report_file.open("a") as file:
            file.write(str(buy_report_entry))
            file.write(str(sell_report_entry))
        
# =================================================================================================================

    def create_24_hour_report_entry(self, price, symbol, action, submit_time, execution_time, ask_price, bid_price, limit_price):     
        report_entry = TwentyFourReportEntry(
                date=datetime.today().strftime("%m/%d/%Y"),
                program_submitted=submit_time,
                broker_executed=execution_time,
                sym=symbol,
                broker='IB',
                action=action,
                quantity=1,
                price=price,
                spread=0,
                ask=ask_price,
                bid=bid_price,
                limit_price=limit_price
                )

        return report_entry
    
# =================================================================================================================

    '''
    Adds orders that get rejected to the report
    Sets price + spread to 0 to indicate rejection
    '''
    def add_rejected_order_to_report(self, symbol, submit_time, ask_price, bid_price):
        buy_report_entry = TwentyFourReportEntry(
                            date=datetime.today().strftime("%m/%d/%Y"),
                            program_submitted=submit_time,
                            broker_executed=submit_time,
                            sym=symbol,
                            broker='IB',
                            action="BUY",
                            quantity=1,
                            price=0,
                            spread=0, 
                            ask=ask_price,
                            bid=bid_price,
                            limit_price = round(1.01 * ask_price, 2)
                            )
        
        sell_report_entry = TwentyFourReportEntry(
                            date=datetime.today().strftime("%m/%d/%Y"),
                            program_submitted=submit_time,
                            broker_executed=submit_time,
                            sym=symbol,
                            broker='IB',
                            action="SELL",
                            quantity=1,
                            price=0,
                            spread=0,
                            ask=ask_price,
                            bid=bid_price,
                            limit_price = round(0.98 * bid_price, 2)
                            )
        
        # write to report file
        date = datetime.now().strftime("%m_%d")
        report_file = BASE_PATH / f"reports/24_hour/24_report_{date}.csv"
        with report_file.open("a") as file:
            file.write(str(buy_report_entry))
            file.write(str(sell_report_entry))

# =================================================================================================================

    '''
    Adds orders that get rejected to the report
    Sets price + spread to 0 to indicate rejection
    '''
    def add_filled_buy_order_and_rejected_sell_order_to_report(self, symbol, buy_program_submitted, sell_program_submitted, ask_price, bid_price, buy_limit_price):

        buy_execution_filter = ExecutionFilter(symbol=symbol, side="BUY")
        buy_execution = self.ib.reqExecutions(execFilter=buy_execution_filter)[-1].execution
        buy_price = buy_execution.price
        buy_exection_time = buy_execution.time.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%I:%M:%S %p")
        buy_report_entry = self.create_24_hour_report_entry(buy_price, symbol, "BUY", buy_program_submitted, buy_exection_time, ask_price, bid_price, buy_limit_price)
        
        sell_report_entry = TwentyFourReportEntry(
                            date=datetime.today().strftime("%m/%d/%Y"),
                            program_submitted=sell_program_submitted,
                            broker_executed=sell_program_submitted,
                            sym=symbol,
                            broker='IB',
                            action="SELL",
                            quantity=1,
                            price=0,
                            spread=0,
                            ask=ask_price,
                            bid=bid_price, 
                            limit_price=round(0.98*bid_price, 2)
                            )
        
        # print(sell_report_entry)
        
        # write to report file
        date = datetime.now().strftime("%m_%d")
        report_file = BASE_PATH / f"reports/24_hour/24_report_{date}.csv"
        with report_file.open("a") as file:
            file.write(str(buy_report_entry))
            file.write(str(sell_report_entry))

# =================================================================================================================

    def test(self):

        contract = Stock(symbol='AMZN', exchange='SMART', currency='USD')

        # Request real-time market data
        self.ib.reqMktData(contract, genericTickList='', snapshot=False, regulatorySnapshot=False)

        # Wait for market data to be populated
        self.ib.sleep(2)  # Wait briefly to allow data retrieval

        # Access the market data
        ticker = self.ib.ticker(contract)

        print(ticker.last)
        

# =================================================================================================================

    def get_bid_price(self, symbol):
        contract = Stock(symbol=symbol, exchange='SMART', currency='USD')

        # Request real-time market data
        self.ib.reqMktData(contract, genericTickList='', snapshot=False, regulatorySnapshot=False)

        # Wait for market data to be populated
        self.ib.sleep(2)  # Wait briefly to allow data retrieval

        # Access the market data
        ticker = self.ib.ticker(contract)

        return round(ticker.bid, 2)

# =================================================================================================================

    def get_ask_price(self, symbol):
        contract = Stock(symbol=symbol, exchange='SMART', currency='USD')

        # Request real-time market data
        self.ib.reqMktData(contract, genericTickList='', snapshot=False, regulatorySnapshot=False)

        # Wait for market data to be populated
        self.ib.sleep(4)  # Wait briefly to allow data retrieval

        # Access the market data
        ticker = self.ib.ticker(contract)

        return round(ticker.ask, 2)

# =================================================================================================================

    def sell_later_filled_orders(self):
        # logger.info("In sell later filled orders")
        # check open positions for equity
        try:
            positions = self.ib.positions()
            self.ib.sleep(4)
            open_positions = {position.contract.symbol for position in positions}


            # logger.info("Attempting to sell leftovers on IBKR")
            # print(f"Open positions: {open_positions}")
            # print(f"Open buy orders: {self.open_buy_orders}")
            # print(f"Open sell orders: {self.open_sell_orders}")


            for order in self.open_buy_orders:
                if self.open_buy_orders[order] == ():
                    continue
                if order in open_positions:
                    self.sell_limit(order)
                    sell_program_submitted = datetime.now().strftime("%I:%M:%S %p")
                    logger.info(f"Sold {order} on IBKR")

                    buy_program_submitted = self.open_buy_orders[order]
                    self.open_sell_orders[order] = (buy_program_submitted, sell_program_submitted)

                    # print(self.open_sell_orders[order])
                    self.open_buy_orders[order] = ()    # reset dictionary

            for order in self.open_sell_orders:
                if self.open_sell_orders[order] == ():
                    continue

                if order not in open_positions:
                    # how can we get buy program submitted and sell program submitted times?
                    buy_program_submitted = self.open_sell_orders[order][0]
                    sell_program_submitted = self.open_sell_orders[order][1]

                    self.add_to_24_hour_report(order, buy_program_submitted, sell_program_submitted)
                    self.open_sell_orders[order] = ()    # reset dictionary
                    logger.info(f"Added {order} to report for IBKR")
        except Exception as e:
            logger.error("Error selling later filled orders on IBKR")

# =================================================================================================================

    def get_open_positions(self):
        self.ib.sleep(1)
        positions = self.ib.positions()
        open_positions = {position.contract.symbol for position in positions}

        return open_positions

# =================================================================================================================

    def get_correct_market_flag(self):
        from datetime import datetime, time

        # Get the current time
        current_time = datetime.now().time()

        # Define the time ranges
        extended_morning_start = time(1, 0)  # 1:00 AM
        extended_morning_end = time(6, 30)  # 6:30 AM
        extended_afternoon_start = time(13, 0)  # 1:00 PM
        extended_afternoon_end = time(17, 0)  # 4:00 PM
        all_day_start = time(17, 0)  # 5:00 PM
        all_day_end = time(1, 0)  # 1:00 AM THIS MAY NEED TO BE CHANGED

        # Check the conditions for extended hours
        if (extended_morning_start <= current_time <= extended_morning_end or
            extended_afternoon_start <= current_time <= extended_afternoon_end):
            return "extended_hours"

        # Check the conditions for overnight hours
        if (current_time >= all_day_start or current_time < all_day_end):
            return "overnight_hours"

        # Default to regular hours
        return "regular_hours"

# =================================================================================================================

    def sell_24_hour_leftover_positions(self):
        positions = self.get_current_positions()
        # print(positions)
        # for position in positions[0]:
        #     print(position.position)

        for position in positions[0]:
            if int(position.position) >= 1:
                for i in range(int(position.position)):
                    self.sell_limit(position.contract.symbol)

#======================================================================================================
        
    def get_last_traded_price(self, sym):
        '''
        first used Robinhood to get quotes but then stopped due to cease and desist
        then used IBKR to get quotes but stopped so Chris can trade options
        now using etrade!
        '''
        contract = Stock(symbol=sym, exchange='SMART', currency='USD')

        # Request real-time market data
        self.ib.reqMktData(contract, genericTickList='', snapshot=False, regulatorySnapshot=False)

        # Wait for market data to be populated
        self.ib.sleep(1)  # Wait briefly to allow data retrieval

        # Access the market data
        ticker = self.ib.ticker(contract)

        return float(ticker.last)

#======================================================================================================



if __name__ == "__main__":

    a = IBKR(Path("temp.csv"), BrokerNames.IF)
    a.login()
    a.buy_and_sell_immediately("GME")
    # print(a.get_correct_market_flag())
    # a.buy_limit("GME")
    # time.sleep(2)
    # a.sell_limit("GME")
    # print(f"Ask price for AMZN: {a.get_ask_price('AMZN')}")
    # print(f"Bid price for AMZN: {a.get_bid_price('AMZN')}")

    # THERE'S A DISCREPNECY IN THE LENGTHS OF THIS
    # it's because of the added 3:05 time, so let's figure out what the group
    # number is for 3:10 and then add to the group assignmetns
    # trade_all_symbols_times = ["12:30", "12:50", "13:10", "14:10", "15:10", "16:10", "16:50",
    #                 "17:10", "18:10", "19:10", "20:10", "21:10", "22:10", "23:10",
    #                 "00:10", "00:40", "01:10", "02:10", "03:05", "03:10", "04:10", "04:50",
    #                 "05:10","06:10", "06:40", "07:00"]
    

    # group_assignment = [
    #     1, 
    #     1, 
    #     1, 
    #     2, 
    #     3, 
    #     4, 
    #     5, 
    #     5, 
    #     6, 
    #     7, 
    #     8, 
    #     9,
    #     1, 
    #     2, 
    #     3, 
    #     4, 
    #     4, 
    #     5, 
    #     6,
    #     6, 
    #     7, 
    #     8, 
    #     8, 
    #     9,
    #     9, 
    #     9
    #     ]

    # print(len(trade_all_symbols_times))
    # print(len(group_assignment))
    # a = IBKR(Path("temp.csv"), BrokerNames.IF)
    # a.login()
    # a.sell_24_hour_leftover_positions()

    # a.test()
    # print(a.get_last_traded_price("NVDA"))

    # Symbol list for short selling Chris wanted to do
    # short_sell_sym_list = ["NGVC", "GPRK", "INFU", "TATT", "GSIT", "ULY", "TLF", "SCKT", "EVOK", "PWM"]
    # short_sell_sym_list = ['TRGP', 'GIC', 'FRAF', 'ANTX', 'VZLA', 'BRFH', 'HITI', 'CELZ', 'RAIN', 'PNBK']
    # short_sell_sym_list = ['ANTX', 'VZLA', 'BRFH', 'HITI', 'CELZ', 'RAIN', 'PNBK']
    # short_sell_sym_list = ['FRAF']

    # for sym in short_sell_sym_list:
    #     try:
    #         a.sell_limit(sym)
    #     except:
    #         print(f"Unable to sell {sym}")



    # a.sell_later_filled_orders()
    # print(a.get_correct_market_flag())

    # option = OptionOrder(sym='MU', option_type=OptionType.CALL, strike='107.00', expiration='2025-01-31', order_type=OrderType.MARKET, quantity=1)
    # a.sell_option(option)

    # MANUAL SELL:
    # open_positions = ["AMZN", "FBTC", "HES", "ASO"]
    # for symbol in open_positions:
    #     a.sell_limit(symbol)


    # a.buy_and_sell_immediately("BBY")
    # a.sell_limit("HES")
    # a.sell_limit("GPC")
    # a.sell_limit("GPC")
    # print(a.get_open_positions())




    # a.sell_later_filled_orders()
    # a.test()














    # a.buy_and_sell_immediately("AAPL")
    # a.test()

    # print("IBKR")
    # def print_bid_and_ask(symbols):
    #     for symbol in symbols:
    #         print(symbol)
    #         print(a.get_bid_price(symbol))
    #         print(a.get_ask_price(symbol))
    #         print('-----------------------------------')

    # sym_list = ["AAPL", "AMZN"]
    # print_bid_and_ask(sym_list)

    # if math.isnan(ask_price):
    #     print('IT IS NAN')
    #     ask_price = a.get_ask_price("BBY")
    # print(type(ask_price))

    # a.sell_later_filled_orders()

    # a.disconnect()

    # Tickers that don't get a bid/ask: CTRA, ENVX



    
