import json
from datetime import datetime
import re
from pathlib import Path

import numpy as np
import pandas as pd
import robin_stocks.robinhood as rh
from pytz import utc, timezone

from utils.report.report import ActionType


COLUMN_ORDER = ['Date', 'Program Submitted', 'Program Executed', 'Broker Executed', 'Symbol',
                'Broker', 'Action', 'Size', 'Price', 'Dollar Amt', 'Pre Quote', 'Post Quote',
                'Pre Bid', 'Pre Ask', 'Post Bid', 'Post Ask', 'Pre Volume', 'Post Volume',
                'Order Type', 'Split', 'Order ID', 'Activity ID']


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
    if order_data["state"] == "cancelled":
        row[:] = None
        return row
    try:
        utc_time = datetime.strptime(order_data["executions"][0]["timestamp"],
                                     "%Y-%m-%dT%H:%M:%S.%fZ")
    except:
        utc_time = datetime.strptime(order_data["executions"][0]["timestamp"],
                                     "%Y-%m-%dT%H:%M:%SZ")
    now_aware = utc.localize(utc_time)
    pst = now_aware.astimezone(timezone("US/Pacific"))
    row["Broker Executed"] = pst.strftime("%I:%M:%S")
    price = float(order_data["executions"][0]["price"])
    size = float(order_data["executions"][0]["quantity"])

    row["Price"] = price
    row["Size"] = size
    row["Dollar Amt"] = price * size
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
    df = pd.read_csv(ibkr_file)
    df = df.drop(
        ['Acct ID', 'Trade Date/Time', 'Settle Date', "Exchange", 'Proceeds', 'Comm', 'Fee',
         'Code'], axis = 1)
    df["Unnamed: 3"] = pd.to_datetime(df["Unnamed: 3"], format = "%I:%M:%S %p") - pd.Timedelta(
        hours = 3)
    df["Broker Executed"] = df["Unnamed: 3"].dt.strftime('%I:%M:%S')
    df["Quantity"] = pd.to_numeric(df["Quantity"])
    df["Quantity"] = df["Quantity"].abs()
    df["Dollar Amt"] = df["Quantity"] * df["Price"]
    df = df.rename(columns = {
        "Type": "Action",
        "Quantity": "Size"
    })
    return df


def get_schwab_report(schwab_file):
    with open(schwab_file, "r") as file:
        df = pd.read_csv(file)
        df_sub = df.drop(columns = ["Description", "Fees & Comm", "Amount"])
        df_sub["Price"] = pd.to_numeric(df_sub["Price"].str[1:])
        df_sub["Dollar Amt"] = (df_sub["Quantity"] * df_sub["Price"]).round(4)
        df_sub = df_sub.rename(columns = {
            "Quantity": "Size"
        })
        return df_sub


def create_datetime_from_string(date_string):
    # Use regular expression to extract month and day values
    if isinstance(date_string, Path):
        date_string = str(date_string)
    parts = date_string.split("_")
    month = int(parts[1])
    day = int(parts[2][:2])

    # Create a datetime object with the extracted month and day
    datetime_obj = datetime(datetime.now().year, month, day)
    return datetime_obj


def parse_etrade_report(df):
    df["Date & Time"] = pd.to_datetime(df["Date & Time"], format = "%m/%d/%y %I:%M:%S %p EDT")
    df["Date & Time"] = df["Date & Time"] - pd.Timedelta(hours = 3)

    df[["Action", "Symbol"]] = df["Order Description"].str.split(expand = True)[[0, 2]]

    df = df.drop(columns = ["Order Description", "Commission/Fee", "Transaction Status"])
    df = df.drop([0])

    df["Price Executed"] = pd.to_numeric(df["Price Executed"])
    df["Dollar Amt"] = df["Quantity"] * df["Price Executed"]

    df["Broker Executed"] = df["Date & Time"].dt.strftime('%I:%M:%S')

    df = df.rename(columns = {
        "Quantity": "Size",
        "Price Executed": "Price",
    })
    return df


def merge_etrade_report(report_df, etrade_df, et_acc):
    merged = pd.merge(left = report_df, right = etrade_df,
                      on = ["Date", "Symbol", "Action", "Broker"])
    merged["Split"] = True
    merged = merged.drop(columns = ["Size_x", "Price_x", "Dollar Amt_x", "Broker Executed_x"])
    merged = merged.rename(columns = {
        "Size_y": "Size",
        "Price_y": "Price",
        "Dollar Amt_y": "Dollar Amt",
        "Broker Executed_y": "Broker Executed"
    })

    merged = merged.reindex(columns = COLUMN_ORDER)
    et = report_df[report_df["Broker"] == et_acc]
    report_df = report_df.drop(et[et["Order ID"].isin(merged["Order ID"])].index)
    report_df = pd.concat([report_df, merged], ignore_index = True)

    return report_df
