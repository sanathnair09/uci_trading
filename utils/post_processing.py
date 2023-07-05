import json
import time
from datetime import datetime

import pandas as pd
import robin_stocks.robinhood as rh
from pytz import utc, timezone

from brokers import RH_LOGIN, RH_PASSWORD


def convert_int64_utc_to_pst(int64):
    utc_datetime = datetime.utcfromtimestamp(float(int64) / 1000)
    now_aware = utc.localize(utc_datetime)
    pst = now_aware.astimezone(timezone("US/Pacific"))
    return pst.strftime("%H:%M:%S")


def get_robinhood_data(row):
    order_data = rh.get_stock_order_info(row["Order ID"])
    utc_time = datetime.strptime(order_data["executions"][0]["timestamp"],
                                 "%Y-%m-%dT%H:%M:%S.%fZ")
    now_aware = utc.localize(utc_time)
    pst = now_aware.astimezone(timezone("US/Pacific"))
    row["Broker Executed"] = pst.strftime("%I:%M:%S")
    row["Price"] = float(order_data["average_price"])
    row["No. of Shares"] = float(order_data["cumulative_quantity"])
    row["Dollar Amt"] = float(order_data["total_notional"]["amount"])
    return row


def format_execution_times(row):
    row["Program Submitted Text"] = datetime.strptime(row["Program Submitted"], "%X:%f").strftime(
        "%X %p")
    row["Program Executed Text"] = datetime.strptime(row["Program Executed"], "%X:%f").strftime(
        "%X %p")
    if row["Broker Executed"]:
        row["Broker Executed Text"] = datetime.strptime(row["Broker Executed"],
                                                        "%I:%M:%S").strftime("%X %p")
    return row


def calculate_rounded_price(price):
    if price:
        price = float(price)
        return round(round(price, 2) - price, 4)
    return price


def data_post_processing(report_file: str):
    print("File: ", f"reports/report_{datetime.now().strftime('%m_%d')}.csv")

    start = time.time()

    rh.login(RH_LOGIN, RH_PASSWORD)
    df = pd.read_csv(report_file)
    df = df.fillna('')
    df = df.replace(-1, '')

    # get Robinhood data
    df.loc[df['Broker'] == "RH"] = df.loc[df['Broker'] == "RH"].apply(get_robinhood_data, axis = 1)

    # convert Etrade time to human-readable format
    df.loc[df['Broker'] == "ET", 'Broker Executed'] = df.loc[
        df['Broker'] == "ET", 'Broker Executed'].apply(
        lambda int64_time: convert_int64_utc_to_pst(int64_time))

    # calculate misc
    price_idx = df.columns.get_loc("Price")
    df.insert(price_idx + 1, "Rounded Price - Price", 0.0)
    df.loc[:, "Rounded Price - Price"] = df.loc[:, "Price"].apply(calculate_rounded_price)
    df.insert(price_idx + 2, "Subpenny", 0)
    df.loc[:, "Subpenny"] = df.loc[:, "Rounded Price - Price"].apply(
        (lambda diff: 1 if diff != 0 else 0))

    # type casting and rounding
    df["Size"] = df["Size"].replace('', 0)
    df = df.astype({"Size": int})
    df["Size"] = df["Size"].replace(0, '')


    # time formatting - add text columns next to numeric time
    program_submitted_idx = df.columns.get_loc("Program Submitted")
    df.insert(program_submitted_idx + 1, "Program Submitted Text", "")

    program_executed_idx = df.columns.get_loc("Program Executed")
    df.insert(program_executed_idx + 1, "Program Executed Text", "")

    broker_executed_idx = df.columns.get_loc("Broker Executed")
    df.insert(broker_executed_idx + 1, "Broker Executed Text", "")

    df = df.apply(format_execution_times, axis = 1)

    df.to_csv(f"reports/report_{datetime.now().strftime('%m_%d')}_filtered.csv", index = False)

    end = time.time()
    print(end - start)


if __name__ == '__main__':
    # data_post_processing("../reports/report_06_30.csv")
    pass
