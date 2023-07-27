import time
from datetime import datetime, timedelta

import pandas as pd
import robin_stocks.robinhood as rh
from pytz import utc, timezone

from brokers import RH_LOGIN, RH_PASSWORD, ETrade
from utils.report import ActionType, BrokerNames


def convert_int64_utc_to_pst(int64):
    try:
        utc_datetime = datetime.utcfromtimestamp(float(int64) / 1000)
        now_aware = utc.localize(utc_datetime)
        pst = now_aware.astimezone(timezone("US/Pacific"))
        return pst.strftime("%H:%M:%S")
    except:
        return int64


def get_robinhood_data(row):
    order_data = rh.get_stock_order_info(row["Order ID"])
    try:
        utc_time = datetime.strptime(order_data["executions"][0]["timestamp"],
                                     "%Y-%m-%dT%H:%M:%S.%fZ")
    except:
        utc_time = datetime.strptime(order_data["executions"][0]["timestamp"],
                                     "%Y-%m-%dT%H:%M:%SZ")
    now_aware = utc.localize(utc_time)
    pst = now_aware.astimezone(timezone("US/Pacific"))
    row["Broker Executed"] = pst.strftime("%I:%M:%S")
    row["Price"] = float(order_data["average_price"])
    row["Size"] = float(order_data["cumulative_quantity"])
    row["Dollar Amt"] = float(order_data["total_notional"]["amount"])
    return row


def format_execution_times(row):
    row["Program Submitted Text"] = datetime.strptime(str(row["Program Submitted"]),
                                                      "%X:%f").strftime(
        "%X %p")
    row["Program Executed Text"] = datetime.strptime(str(row["Program Executed"]),
                                                     "%X:%f").strftime(
        "%X %p")
    if row["Broker Executed"]:
        row["Broker Executed Text"] = datetime.strptime(str(row["Broker Executed"]),
                                                        "%I:%M:%S").strftime("%X %p")
    return row


def calculate_rounded_price(price):
    if price:
        price = float(price)
        return round(round(price, 2) - price, 4)
    return price


def calculate_price_improvement(row):
    if row["Price"]:
        action = row["Action"]
        if action == ActionType.BUY.value:
            # price lower than sellers min
            return 1 if row["Price"] < row["Pre Ask"] else 0
        else:
            # price higher than buyers max
            return 1 if row["Price"] > row["Pre Bid"] else 0
    return ""


def calculate_subpenny_and_fractionalpino5(rounded_price):
    # fractional -> =IF(OR(M5=0,ABS(ROUND(M5,4))=0.005),0,1)
    if rounded_price != "":
        subpenny = 1 if rounded_price != 0 else 0
        fractionalpino5 = 0 if abs(rounded_price) == 0.005 else 1
        return pd.Series([subpenny, fractionalpino5], index = ["Subpenny", "FractionalPIno5"])
    return pd.Series(["", ""], index = ["Subpenny", "FractionalPIno5"])


def calculate_BJZZ_flag(rounded_price):
    # =IF(AND(ABS(M2)<0.004,ABS(M2)>0),1,0)
    if rounded_price != "":
        return 1 if 0 < abs(rounded_price) < 0.004 else 0
    return ""


def calculate_correct_and_wrong(row):
    # correct: =IF(OR(AND(J5=1,M5>0,M5<0.004),AND(J5=-1,M5>-0.004,M5<0)),1,0)
    # wrong: =IF(Q2=1,IF(R2=1,0,1),0) , Q2 = BJZZ Flag
    rounded_price = row["Rounded Price - Price"]
    action = row["Action"]
    bjzz_flag = row["BJZZ Flag"]
    if rounded_price != "":
        correct = 1 if (action == ActionType.BUY.value and 0 < rounded_price < 0.04) or (
                action == ActionType.SELL.value and -0.004 < rounded_price < 0) else 0
        wrong = int(not correct) if bjzz_flag == 1 else 0
        return pd.Series([correct, wrong], index = ["Correct", "Wrong"])
    return pd.Series(["", ""], index = ["Correct", "Wrong"])


def calculate_categories(row):
    # =IF(AND(P6=1,R6=0),IF(AND(ABS(M6)<=0.005,ABS(M6)>0.004),3,2),IF(R6=1,4,IF(P6=0,1)))
    # P6 = fractional, R6 = correct, m6 = rounded_price
    rounded_price = row["Rounded Price - Price"]
    fractional_pino5 = row["FractionalPIno5"]
    correct = row["Correct"]
    if rounded_price != "":
        if fractional_pino5 == 1 and correct == 1:
            return 3 if 0.004 < abs(rounded_price) <= 0.005 else 2
        else:
            return 4 if fractional_pino5 == 1 else 1


def calculate_bjzz(rounded_price):
    # =IF(AND(M2>0,M2<0.004),1,IF(AND(M2<0,M2>-0.004),-1,0))
    if rounded_price != "":
        if 0 < rounded_price < 0.04:
            return 1
        else:
            return -1 if -0.004 < rounded_price < 0 else 0
    return ""


def calculate_tradeID(row):
    bigTrade = row["BigTrade"]
    symbol = row["Symbol"]
    today = datetime.strptime(row["Date"], "%x")
    year, month, day = today.year, today.strftime("%m"), today.strftime("%d")
    return f"{year}{month}{day}{symbol}{'1000' if bigTrade else '0100'}"


def calculate_bidaskspread(row):
    return round(float(row["Pre Ask"]) - float(row["Pre Bid"]), 4)


def calculate_tradelocation(row):
    if row["Price"] and row["BidAskSpread"]:
        return round((float(row["Price"]) - float(row["Pre Bid"])) / row["BidAskSpread"], 4)
    return ""


class PostProcessing:
    def __init__(self, output_file_version = 0):
        self._output_file_version = "" if output_file_version == 0 else output_file_version

        self._brokers = {}

        self._login()

    def _login(self):
        rh.login(RH_LOGIN, RH_PASSWORD)
        self._brokers = {
            'ET': ETrade('', BrokerNames.ET),
            'E2': ETrade('', BrokerNames.E2)
        }
        self._brokers["ET"].login()
        self._brokers["E2"].login()

        print("Finished logging in...")

    def _get_etrade_data(self, row):
        broker = row["Broker"]
        broker_obj: ETrade = None
        if broker == "ET":
            broker_obj = self._brokers["ET"]
        elif broker == "E2":
            broker_obj = self._brokers["E2"]

        from_date = row["Date"]
        formated_date = datetime.strptime(from_date, "%m/%d/%y")
        to_date = formated_date + timedelta(days = 1)

        order_data = broker_obj.get_order_data([row["Symbol"]], row["Order ID"],
                                               from_date = formated_date.strftime("%m%d%Y"),
                                               to_date = to_date.strftime("%m%d%Y"))
        order_data = order_data["OrderDetail"][0]
        price = order_data["Instrument"][0]["averageExecutionPrice"]
        dollar_amt = row["Size"] * price
        row["Price"] = price
        row["Dollar Amt"] = dollar_amt
        return row

    def generate_report(self, report_file):
        print("Processing:", report_file)
        start = time.time()

        df = pd.read_csv(report_file)
        df = df.fillna('')

        # get broker data
        df.loc[df['Broker'] == "RH"] = df.loc[df['Broker'] == "RH"].apply(get_robinhood_data,
                                                                          axis = 1)
        df.loc[(df["Broker"] == "ET") | (df["Broker"] == "E2")] = df.loc[
            (df["Broker"] == "ET") | (df["Broker"] == "E2")].apply(
            lambda row: self._get_etrade_data(row), axis = 1)

        # convert Etrade time to human-readable format
        df.loc[df['Broker'] == "ET", 'Broker Executed'] = df.loc[
            df['Broker'] == "ET", 'Broker Executed'].apply(
            lambda int64_time: convert_int64_utc_to_pst(int64_time))
        df.loc[df['Broker'] == "E2", 'Broker Executed'] = df.loc[
            df['Broker'] == "E2", 'Broker Executed'].apply(
            lambda int64_time: convert_int64_utc_to_pst(int64_time))

        # calculate misc
        price_idx = df.columns.get_loc("Price")
        df.insert(price_idx + 1, "Rounded Price - Price", 0.0)
        df.loc[:, "Rounded Price - Price"] = df.loc[:, "Price"].apply(calculate_rounded_price)

        # bid - highest buyer is willing to buy
        # ask - lowest seller is willing to sell
        df.insert(price_idx + 2, "PriceImprovement",
                  0)  # =IF(OR(AND(J3=1,L3<Z3),AND(L3>Y3,J3=-1)),1,0)
        df.loc[:, "PriceImprovement"] = df.loc[:, ["Action", "Price", "Pre Bid", "Pre Ask"]].apply(
            calculate_price_improvement, axis = 1)

        df.insert(price_idx + 3, "Subpenny", 0)
        df.insert(price_idx + 4, "FractionalPIno5", 0)
        df.loc[:, ["Subpenny", "FractionalPIno5"]] = df.loc[:, "Rounded Price - Price"].apply(
            calculate_subpenny_and_fractionalpino5)

        df.insert(price_idx + 5, "BJZZ Flag", 0)
        df.loc[:, "BJZZ Flag"] = df.loc[:, "Rounded Price - Price"].apply(calculate_BJZZ_flag)

        df.insert(price_idx + 6, "Correct", 0)
        df.insert(price_idx + 7, "Wrong", 0)
        df.loc[:, ["Correct", "Wrong"]] = df.loc[:,
                                          ["Action", "Rounded Price - Price", "BJZZ Flag"]].apply(
            calculate_correct_and_wrong, axis = 1, result_type = "expand")

        df.insert(price_idx + 8, "Categories", 0)
        df.loc[:, "Categories"] = df.loc[:,
                                  ["Rounded Price - Price", "FractionalPIno5", "Correct"]].apply(
            calculate_categories, axis = 1)
        df.insert(price_idx + 9, "BJZZ", 0)
        df.loc[:, "BJZZ"] = df.loc[:, "Rounded Price - Price"].apply(calculate_bjzz)

        post_vol_idx = df.columns.get_loc("Post Volume")
        df.insert(post_vol_idx + 1, "First", 0)
        df.insert(post_vol_idx + 2, "BigTrade", 0)
        df.insert(post_vol_idx + 3, "TradeID", 0)

        df.loc[:, "TradeID"] = df.loc[:, ["Date", "Symbol", "BigTrade"]].apply(calculate_tradeID,
                                                                               axis = 1)

        split_idx = df.columns.get_loc("Split")
        df.insert(split_idx + 1, "BidAskSpread", 0)
        df.insert(split_idx + 2, "TradeLocation", 0)
        df.loc[:, "BidAskSpread"] = df.loc[:, ["Pre Bid", "Pre Ask"]].apply(calculate_bidaskspread,
                                                                            axis = 1)
        df.loc[:, "TradeLocation"] = df.loc[:, ["Pre Bid", "Price", "BidAskSpread"]].apply(
            calculate_tradelocation,
            axis = 1)

        # type casting and rounding
        df[["Size", "Categories"]] = df[["Size", "Categories"]].fillna(0)
        df = df.astype({"Size": int, "Categories": int, "Split": int})
        df[["Size", "Categories"]] = df[["Size", "Categories"]].replace(0, '')

        # time formatting -> add text columns next to numeric time
        program_submitted_idx = df.columns.get_loc("Program Submitted")
        df.insert(program_submitted_idx + 1, "Program Submitted Text", "")

        program_executed_idx = df.columns.get_loc("Program Executed")
        df.insert(program_executed_idx + 1, "Program Executed Text", "")

        broker_executed_idx = df.columns.get_loc("Broker Executed")
        df.insert(broker_executed_idx + 1, "Broker Executed Text", "")

        df = df.apply(format_execution_times, axis = 1)

        underscore_idx = report_file.find("_")
        filetype_idx = report_file.find(".")
        filtered_filename = f'reports/filtered/report{report_file[underscore_idx:filetype_idx]}_filtered{self._output_file_version}.csv'
        df.to_csv(filtered_filename, index = False)

        end = time.time()
        print(end - start, "seconds")
        print("Output file:", filtered_filename)

        ### Report Summary
        print(f"Number of Trades: {len(df['Symbol'].unique())}")


if __name__ == '__main__':
    # PostProcessing("../reports/original/report_07_19.csv", 2)

    pass
