import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd
import robin_stocks.robinhood as rh
from pytz import utc, timezone

from brokers import RH_LOGIN, RH_PASSWORD, ETrade, Fidelity, BASE_PATH
from utils.report.report import ActionType, BrokerNames
from utils.report.report_utils import get_ibkr_report, get_schwab_report, \
    create_datetime_from_string, get_robinhood_data, convert_int64_utc_to_pst, \
    vectorized_calculate_rounded_price, optimized_calculate_price_improvement, \
    optimized_calculate_subpenny_and_fractionalpino5, optimized_calculate_BJZZ_flag, \
    optimized_calculate_correct_and_wrong, optimized_calculate_categories, optimized_calculate_bjzz


def check_file_existence(file_path):
    path = Path(file_path)
    return path.exists() and path.is_file()


class PostProcessing:
    def __init__(self, output_file_version = 0):
        self._output_file_version = "" if output_file_version == 0 else output_file_version

        self._brokers = {}

        self._login()

    def _login(self):
        rh.login(RH_LOGIN, RH_PASSWORD)
        self._brokers = {
            'ET': ETrade('', BrokerNames.ET),
            'E2': ETrade('', BrokerNames.E2),
            'FD': Fidelity('', BrokerNames.FD)
        }
        self._brokers["ET"].login()
        self._brokers["E2"].login()
        self._brokers["FD"].login()

        print("Finished logging in...")

        print("Downloading Fidelity Splits")
        self._brokers["FD"].download_trade_data()

    def _get_etrade_data(self, row):
        broker = row["Broker"]
        broker_obj: Union[ETrade, None] = None
        if broker == "ET":
            broker_obj = self._brokers["ET"]
        elif broker == "E2":
            broker_obj = self._brokers["E2"]

        from_date = row["Date"]
        formatted_date = datetime.strptime(from_date, "%m/%d/%y")
        to_date = formatted_date + timedelta(days = 1)

        order_data = broker_obj.get_order_data([row["Symbol"]], row["Order ID"],
                                               from_date = formatted_date.strftime("%m%d%Y"),
                                               to_date = to_date.strftime("%m%d%Y"))
        if order_data:
            order_data = order_data["OrderDetail"][0]
            price = order_data["Instrument"][0]["averageExecutionPrice"]
            dollar_amt = row["Size"] * price
            row["Price"] = price
            row["Dollar Amt"] = dollar_amt
        else:
            print(row["Order ID"])
        return row

    def _get_broker_data(self, date):

        ibkr_file = BASE_PATH / f"data/ibkr/DailyTradeReport.{date.strftime('%Y%m%d')}.html"
        fidelity_file = BASE_PATH / f"data/fidelity/fd_splits_{date.strftime('%m_%d')}.csv"
        schwab_file = BASE_PATH / f"data/schwab/schwab_{date.strftime('%m_%d')}.json"

        ibkr_df = get_ibkr_report(ibkr_file) if check_file_existence(ibkr_file) else None
        fidelity_df = pd.read_csv(fidelity_file) if check_file_existence(fidelity_file) else \
            self._brokers["FD"].get_trade_data()
        schwab_df = get_schwab_report(schwab_file) if check_file_existence(
            schwab_file) else None  # TODO: parse schwab data

        if isinstance(fidelity_df, pd.DataFrame):
            fidelity_df["Broker Executed"] = pd.to_datetime(fidelity_df["Broker Executed"], format = "%Y-%m-%d %H:%M:%S")

        return ibkr_df, fidelity_df, schwab_df  # IBKR, Fidelity, Schwab

    def optimized_generate_report(self, report_file):
        print("Processing:", report_file)
        start = time.time()

        formatted_date = create_datetime_from_string(report_file)
        ibkr_df, fidelity_df, schwab_df = self._get_broker_data(formatted_date)

        df = pd.read_csv(report_file)

        # get broker data

        def parse_broker_data(row, broker):
            symbol = row["Symbol"]
            action = row["Action"]

            if broker == "IF":
                hour = row["Broker Executed"].strftime("%I")
                report_row = df[
                    (df["Broker"] == broker) & (df["Symbol"] == symbol) & (
                            df["Action"] == action) & (df["Program Submitted"].str[:2] == hour)]
            else:
                report_row = df[
                    (df["Broker"] == broker) & (df["Symbol"] == symbol) & (df["Action"] == action)]

            if report_row.shape[0]:
                if report_row.shape[0] > 1:
                    report_row = report_row.iloc[0]

                if broker != "SB": # schwab doesn't provide exact execution time
                    report_row["Broker Executed"] = row["Broker Executed"].strftime("%X")
                report_row["Size"] = row["Quantity"]
                report_row["Price"] = row["Price"]
                report_row["Dollar Amt"] = row["Dollar Amt"]
                return report_row.squeeze()

        if isinstance(ibkr_df, pd.DataFrame):
            new_ibkr_entries = ibkr_df.apply(parse_broker_data, broker = "IF", axis = 1)
            new_ibkr_entries = new_ibkr_entries[
                new_ibkr_entries["Date"].notna()]  # remove any possible null rows
            df.drop((df[df["Broker"] == "IF"]).index, inplace = True)  # remove all IBKR entries
            df = pd.concat([df, new_ibkr_entries], ignore_index = True)

        if isinstance(fidelity_df, pd.DataFrame):
            fidelity_splits = fidelity_df.apply(parse_broker_data, broker = "FD", axis = 1)
            df.drop((df[df["Broker"] == "FD"]).index, inplace = True)
            df = pd.concat([df, fidelity_splits], ignore_index = True)

        if isinstance(schwab_df, pd.DataFrame):
            schwab_data = schwab_df.apply(parse_broker_data, broker = "SB", axis = 1)
            df.drop((df[df["Broker"] == "SB"]).index, inplace = True)
            df = pd.concat([df, schwab_data], ignore_index = True)

        df.loc[df['Broker'] == "RH"] = df.loc[df['Broker'] == "RH"].apply(get_robinhood_data,
                                                                          axis = 1)
        df.loc[(df["Broker"] == "ET") | (df["Broker"] == "E2")] = df.loc[
            (df["Broker"] == "ET") | (df["Broker"] == "E2")].apply(
            lambda row: self._get_etrade_data(row), axis = 1)

        df.loc[(df['Broker'] == "ET") | (df['Broker'] == "E2"), 'Broker Executed'] = df.loc[
            (df['Broker'] == "ET") | (df['Broker'] == "E2"), 'Broker Executed'].apply(
            lambda int64_time: convert_int64_utc_to_pst(int64_time))

        df["Date"] = pd.to_datetime(df["Date"])
        df["Program Submitted"] = pd.to_datetime(df["Program Submitted"], format = '%X:%f')
        df["Program Executed"] = pd.to_datetime(df["Program Executed"], format = '%X:%f')
        df["Broker Executed"] = pd.to_datetime(df["Broker Executed"], format = "%X")

        # calculate misc

        price_idx = df.columns.get_loc("Price")
        df.insert(price_idx + 1, "Rounded Price - Price", '')
        df["Rounded Price - Price"] = vectorized_calculate_rounded_price(
            df["Price"].to_numpy(dtype = 'float64'))

        # bid - highest buyer is willing to buy
        # ask - lowest seller is willing to sell

        # =IF(OR(AND(J3=1,L3<Z3),AND(L3>Y3,J3=-1)),1,0)
        df.insert(price_idx + 2, "PriceImprovement", '')
        df.loc[df["Price"].notna(), "PriceImprovement"] = df.loc[
            df["Price"].notna(), ["Action", "Price", "Pre Bid", "Pre Ask"]].apply(
            optimized_calculate_price_improvement, axis = 1)

        df.insert(price_idx + 3, "Subpenny", '')
        df.insert(price_idx + 4, "FractionalPIno5", '')
        df.loc[df["Rounded Price - Price"].notna(), ["Subpenny", "FractionalPIno5"]] = df.loc[
            df["Rounded Price - Price"].notna(), "Rounded Price - Price"].apply(
            optimized_calculate_subpenny_and_fractionalpino5)

        df.insert(price_idx + 5, "BJZZ Flag", '')
        df.loc[df["Rounded Price - Price"].notna(), "BJZZ Flag"] = df.loc[
            df["Rounded Price - Price"].notna(), "Rounded Price - Price"].apply(
            optimized_calculate_BJZZ_flag)

        df.insert(price_idx + 6, "Correct", '')
        df.insert(price_idx + 7, "Wrong", '')
        df.loc[df["Rounded Price - Price"].notna(), ["Correct", "Wrong"]] = df.loc[
            df["Rounded Price - Price"].notna(),
            ["Action", "Rounded Price - Price", "BJZZ Flag"]].apply(
            optimized_calculate_correct_and_wrong, axis = 1, result_type = "expand")

        df.insert(price_idx + 8, "Categories", '')
        df.loc[df["Rounded Price - Price"].notna(), "Categories"] = df.loc[
            df["Rounded Price - Price"].notna(),
            ["Rounded Price - Price", "FractionalPIno5", "Correct"]].apply(
            optimized_calculate_categories, axis = 1)

        df.insert(price_idx + 9, "BJZZ", '')
        df.loc[df["Rounded Price - Price"].notna(), "BJZZ"] = df.loc[
            df["Rounded Price - Price"].notna(), "Rounded Price - Price"].apply(
            optimized_calculate_bjzz)

        post_vol_idx = df.columns.get_loc("Post Volume")
        df.insert(post_vol_idx + 1, "First", 0)
        df.insert(post_vol_idx + 2, "BigTrade", 0)
        df.insert(post_vol_idx + 3, "TradeID", '')

        df["TradeID"] = df["Date"].dt.year.astype(str) + df["Date"].dt.month.map(
            "{:02}".format).astype(str) + df["Date"].dt.day.astype(str) + df["Symbol"] + np.where(
            df["BigTrade"].to_numpy(dtype = "int64") == 0, "0100", "100")

        split_idx = df.columns.get_loc("Split")
        df.insert(split_idx + 1, "BidAskSpread", '')
        df.insert(split_idx + 2, "TradeLocation", '')
        df["BidAskSpread"] = (df["Pre Ask"] - df["Pre Bid"]).round(4)

        df["TradeLocation"] = ((df["Price"] - df["Pre Bid"]) / df["BidAskSpread"]).round(4)

        # time formatting -> add text columns next to numeric time
        program_submitted_idx = df.columns.get_loc("Program Submitted")
        df.insert(program_submitted_idx + 1, "Program Submitted Text", "")

        program_executed_idx = df.columns.get_loc("Program Executed")
        df.insert(program_executed_idx + 1, "Program Executed Text", "")

        broker_executed_idx = df.columns.get_loc("Broker Executed")
        df.insert(broker_executed_idx + 1, "Broker Executed Text", "")

        df["Program Submitted Text"] = df["Program Submitted"].dt.strftime("%X %p")
        df["Program Executed Text"] = df["Program Executed"].dt.strftime("%X %p")
        df["Broker Executed Text"] = df["Broker Executed"].dt.strftime("%X %p")

        # type casting and rounding
        # df = df.astype({
        #     "Size": int,
        #     "Split": int,
        # })
        df["Date"] = df["Date"].dt.strftime('%m/%d/%Y')
        df["Program Submitted"] = df["Program Submitted"].dt.strftime('%X:%f')
        df["Program Executed"] = df["Program Executed"].dt.strftime('%X:%f')
        df["Broker Executed"] = df["Broker Executed"].dt.strftime("%X")

        underscore_idx = report_file.find("_")
        filetype_idx = report_file.find(".")
        filtered_filename = f'reports/filtered/report{report_file[underscore_idx:filetype_idx]}_filtered{self._output_file_version}.csv'
        df.to_csv(filtered_filename, index = False)

        end = time.time()
        print(end - start, "seconds")
        print("Output file:", filtered_filename)

        print(f"Number of Trades: {len(df['Symbol'].unique())}")


if __name__ == '__main__':
    processor = PostProcessing()
    processor.optimized_generate_report(f"../../reports/original/report_08_15.csv",
                                        )
    # processor.optimized_generate_report(f"../../reports/original/report_08_16.csv",
    #                                     ibkr_prices_file = '../../data/ibkr/original/DailyTradeReport.20230816.html',
    #                                     get_fidelity = False)
    # processor.optimized_generate_report(f"../../reports/original/report_08_17.csv",
    #                                     ibkr_prices_file = '../../data/ibkr/original/DailyTradeReport.20230817.html',
    #                                     fidelity_splits_file = '../../data/fidelity/fd_splits_08_17.csv')
    # processor.optimized_generate_report(f"../../reports/original/report_08_18.csv",
    #                                     ibkr_prices_file = '../../data/ibkr/original/DailyTradeReport.20230818.html',
    #                                     fidelity_splits_file = '../../data/fidelity/fd_splits_08_18.csv')
    # processor.optimized_generate_report(f"../../reports/original/report_08_21.csv",
    #                                     ibkr_prices_file = '../../data/ibkr/original/DailyTradeReport.20230821.html',
    #                                     fidelity_splits_file = 'data/fidelity/fd_splits_08_21.csv')
    pass
