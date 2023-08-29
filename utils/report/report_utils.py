import json
from datetime import datetime
import re

import numpy as np
import pandas as pd
import robin_stocks.robinhood as rh
from pytz import utc, timezone

from utils.report.report import ActionType


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


def vectorized_calculate_rounded_price(price_array):
    return np.round(np.round(price_array, 2) - price_array, 4)


def optimized_calculate_price_improvement(row):
    action = row["Action"]
    if action == ActionType.BUY.value:
        # price lower than sellers min
        return 1 if row["Price"] < row["Pre Ask"] else 0
    else:
        # price higher than buyers max
        return 1 if row["Price"] > row["Pre Bid"] else 0


def optimized_calculate_subpenny_and_fractionalpino5(rounded_price):
    # fractional -> =IF(OR(M5=0,ABS(ROUND(M5,4))=0.005),0,1)
    subpenny = 1 if rounded_price != 0 else 0
    fractionalpino5 = 0 if abs(rounded_price) == 0.005 else 1
    return pd.Series([subpenny, fractionalpino5], index = ["Subpenny", "FractionalPIno5"])


def optimized_calculate_BJZZ_flag(rounded_price):
    # =IF(AND(ABS(M2)<0.004,ABS(M2)>0),1,0)
    return 1 if 0 < abs(rounded_price) < 0.004 else 0


def optimized_calculate_correct_and_wrong(row):
    # correct: =IF(OR(AND(J5=1,M5>0,M5<0.004),AND(J5=-1,M5>-0.004,M5<0)),1,0)
    # wrong: =IF(Q2=1,IF(R2=1,0,1),0) , Q2 = BJZZ Flag
    rounded_price = row["Rounded Price - Price"]
    action = row["Action"]
    bjzz_flag = row["BJZZ Flag"]
    correct = 1 if (action == ActionType.BUY.value and 0 < rounded_price < 0.04) or (
            action == ActionType.SELL.value and -0.004 < rounded_price < 0) else 0
    wrong = int(not correct) if bjzz_flag == 1 else 0
    return pd.Series([correct, wrong], index = ["Correct", "Wrong"])


def optimized_calculate_categories(row):
    # =IF(AND(P6=1,R6=0),IF(AND(ABS(M6)<=0.005,ABS(M6)>0.004),3,2),IF(R6=1,4,IF(P6=0,1)))
    # P6 = fractional, R6 = correct, m6 = rounded_price
    rounded_price = row["Rounded Price - Price"]
    fractional_pino5 = row["FractionalPIno5"]
    correct = row["Correct"]
    if fractional_pino5 == 1 and correct == 1:
        return 3 if 0.004 < abs(rounded_price) <= 0.005 else 2
    else:
        return 4 if fractional_pino5 == 1 else 1


def optimized_calculate_bjzz(rounded_price):
    # =IF(AND(M2>0,M2<0.004),1,IF(AND(M2<0,M2>-0.004),-1,0))
    if 0 < rounded_price < 0.04:
        return 1
    else:
        return -1 if -0.004 < rounded_price < 0 else 0


def get_ibkr_report(ibkr_file):
    df = pd.read_html(ibkr_file)
    df = df[1]
    df.drop(index = df.index[:2], inplace = True)
    df_sub = df[["Trade Date/Time", "Symbol", "Quantity", "Price", "Code"]]
    df_sub = df_sub[df_sub["Code"].notna()]
    df_sub["Code"] = df_sub["Code"].str[0]
    df_sub["Action"] = np.where(df_sub["Code"] == "O", "Buy", "Sell")
    df_sub = df_sub.drop("Code", axis = 1)
    df_sub = df_sub.drop(df.index[-1])
    df_sub["Trade Date/Time"] = pd.to_datetime(df_sub["Trade Date/Time"])
    df_sub["Trade Date/Time"] = df_sub["Trade Date/Time"] - pd.Timedelta(hours = 3)
    df_sub = df_sub.set_axis(["Broker Executed", "Symbol", "Quantity", "Price", "Action"], axis = 1)
    df_sub["Quantity"] = df_sub["Quantity"].astype("int64").abs()
    df_sub["Price"] = df_sub["Price"].astype("float64")
    df_sub["Dollar Amt"] = (df_sub["Price"] * df_sub["Quantity"]).abs().round(2)
    return df_sub


def get_schwab_report(schwab_file):
    with open(schwab_file, "r") as file:
        data = json.load(file)
        stringify = json.dumps(data["brokerageTransactions"])
        df = pd.read_json(stringify)
        df_sub = df[["transactionDate", "action", "symbol", "shareQuantity", "executionPrice"]]
        df_sub = df_sub.rename(columns = {
            "transactionDate": "Broker Executed",
            "action": "Action",
            "symbol": "Symbol",
            "shareQuantity": "Quantity",
            "executionPrice": "Price"
        })
        df_sub["Price"] = df_sub["Price"].str[1:].astype("float64")
        df_sub["Dollar Amt"] = df_sub["Price"] * df_sub["Quantity"]
        return df_sub

def create_datetime_from_string(date_string):
    # Use regular expression to extract month and day values
    match = re.search(r"report_(\d{2})_(\d{2})", date_string)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))

        # Create a datetime object with the extracted month and day
        datetime_obj = datetime(datetime.now().year, month, day)
        return datetime_obj
    else:
        print("Invalid input string format")
        return None
