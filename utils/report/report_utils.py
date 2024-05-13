from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, cast

import numpy as np
import pandas as pd
import robin_stocks.robinhood as rh  # type: ignore[import-untyped]
from loguru import logger
from pytz import utc, timezone

from utils.report.report import ActionType


def check_file_existence(file_path: Path) -> bool:
    return file_path.exists() and file_path.is_file()


def convert_int64_utc_to_pst(int64: int) -> Union[str, int]:
    try:
        utc_datetime = datetime.utcfromtimestamp(float(int64) / 1000)
        now_aware = utc.localize(utc_datetime)
        pst = now_aware.astimezone(timezone("US/Pacific"))
        return pst.strftime("%H:%M:%S")
    except:
        return int64


def get_robinhood_data(row: pd.Series) -> pd.Series:
    order_data: Any = rh.get_stock_order_info(row["Order ID"])
    if order_data["state"] == "cancelled":
        row[:] = None
        return row
    try:
        utc_time = datetime.strptime(
            order_data["executions"][0]["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
    except:
        utc_time = datetime.strptime(
            order_data["executions"][0]["timestamp"], "%Y-%m-%dT%H:%M:%SZ"
        )
    now_aware = utc.localize(utc_time)
    pst = now_aware.astimezone(timezone("US/Pacific"))
    row["Broker Executed"] = pst.strftime("%I:%M:%S")
    price = float(order_data["executions"][0]["price"])
    size = float(order_data["executions"][0]["quantity"])

    row["Price"] = price
    row["Size"] = size
    row["Dollar Amt"] = round(price * size, 4)
    return row


def get_robinhood_option_data(row: pd.Series) -> pd.Series:
    order_data: Any = rh.get_option_order_info(row["Order ID"])
    if order_data["state"] == "cancelled":
        row[:] = None
        return row
    try:
        utc_time = datetime.strptime(
            order_data["legs"][0]["executions"][0]["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
    except:
        utc_time = datetime.strptime(
            order_data["legs"][0]["executions"][0]["timestamp"], "%Y-%m-%dT%H:%M:%SZ"
        )
    now_aware = utc.localize(utc_time)
    pst = now_aware.astimezone(timezone("US/Pacific"))
    row["Broker Executed"] = pst.strftime("%I:%M:%S")
    price = float(order_data["legs"][0]["executions"][0]["price"])
    quantity = float(order_data["legs"][0]["executions"][0]["quantity"])

    row["Price"] = price
    row["Dollar Amt"] = round(price * quantity * 100, 4)
    row["Strike"] = order_data["legs"][0]["strike_price"]
    row["Option Type"] = order_data["legs"][0]["option_type"].capitalize()
    row["Expiration"] = order_data["legs"][0]["expiration_date"]
    return row


def vectorized_calculate_rounded_price(price_array: np.ndarray) -> np.ndarray:
    return cast(np.ndarray, np.round(np.round(price_array, 2) - price_array, 4))


def optimized_calculate_price_improvement(row: pd.Series) -> int:
    action = row["Action"]
    if action == ActionType.BUY.value:
        # price lower than sellers min
        return 1 if row["Price"] < row["Pre Ask"] else 0
    else:
        # price higher than buyers max
        return 1 if row["Price"] > row["Pre Bid"] else 0


def optimized_calculate_subpenny_and_fractionalpino5(
    rounded_price: pd.Series,
) -> pd.Series:
    # fractional -> =IF(OR(M5=0,ABS(ROUND(M5,4))=0.005),0,1)
    subpenny = 1 if rounded_price != 0 else 0
    fractionalpino5 = 0 if abs(rounded_price) == 0.005 else 1
    return pd.Series([subpenny, fractionalpino5], index=["Subpenny", "FractionalPIno5"])


def optimized_calculate_BJZZ_flag(rounded_price: pd.Series) -> int:
    # =IF(AND(ABS(M2)<0.004,ABS(M2)>0),1,0)
    return 1 if 0 < abs(rounded_price) < 0.004 else 0


def optimized_calculate_correct_and_wrong(row: pd.Series) -> pd.Series:
    # correct: =IF(OR(AND(J5=1,M5>0,M5<0.004),AND(J5=-1,M5>-0.004,M5<0)),1,0)
    # wrong: =IF(Q2=1,IF(R2=1,0,1),0) , Q2 = BJZZ Flag
    rounded_price = row["Rounded Price - Price"]
    action = row["Action"]
    bjzz_flag = row["BJZZ Flag"]
    correct = (
        1
        if (action == ActionType.BUY.value and 0 < rounded_price < 0.04)
        or (action == ActionType.SELL.value and -0.004 < rounded_price < 0)
        else 0
    )
    wrong = int(not correct) if bjzz_flag == 1 else 0
    return pd.Series([correct, wrong], index=["Correct", "Wrong"])


def optimized_calculate_categories(row: pd.Series) -> int:
    # =IF(AND(P6=1,R6=0),IF(AND(ABS(M6)<=0.005,ABS(M6)>0.004),3,2),IF(R6=1,4,IF(P6=0,1)))
    # P6 = fractional, R6 = correct, m6 = rounded_price
    rounded_price = row["Rounded Price - Price"]
    fractional_pino5 = row["FractionalPIno5"]
    correct = row["Correct"]
    if fractional_pino5 == 1 and correct == 1:
        return 3 if 0.004 < abs(rounded_price) <= 0.005 else 2
    else:
        return 4 if fractional_pino5 == 1 else 1


def optimized_calculate_bjzz(rounded_price: pd.Series) -> int:
    # =IF(AND(M2>0,M2<0.004),1,IF(AND(M2<0,M2>-0.004),-1,0))
    if 0 < rounded_price < 0.04:
        return 1
    else:
        return -1 if -0.004 < rounded_price < 0 else 0


def get_ibkr_report(ibkr_file: Path) -> pd.DataFrame:
    df = pd.read_csv(ibkr_file, thousands=",")
    df["Expiration"] = pd.to_datetime(df["Expiration"])
    return df


def get_schwab_report(schwab_file: Path) -> pd.DataFrame:
    df = pd.read_csv(schwab_file)
    df["Date"] = pd.to_datetime(df["Date"])
    if "Expiration" not in df.columns:
        df["Expiration"] = np.nan
        df["Strike"] = np.nan
        df["Option Type"] = np.nan
    else:
        df["Expiration"] = pd.to_datetime(df["Expiration"])
    return df


def get_fidelity_report(fidelity_file: Path) -> pd.DataFrame:
    """
    Returns a DataFrame with the correct dtypes
    """
    df = pd.read_csv(fidelity_file, thousands=",")
    df["Date"] = pd.to_datetime(df["Date"])
    df["Broker Executed"] = pd.to_datetime(df["Broker Executed"], format="%X")
    if "Expiration" not in df.columns:
        df["Expiration"] = np.nan
        df["Strike"] = np.nan
        df["Option Type"] = np.nan
    else:
        df["Expiration"] = pd.to_datetime(df["Expiration"], format="%b-%d-%Y")
    return df


def create_datetime_from_string(date_string: str) -> datetime:
    # Use regular expression to extract month and day values
    if isinstance(date_string, Path):
        date_string = str(date_string)
    parts = date_string.split("_")
    try:
        month = int(parts[1])
        day = int(parts[2][:2])
    except:  # option report
        month = int(parts[2])
        day = int(parts[3][:2])

    # Create a datetime object with the extracted month and day
    datetime_obj = datetime(datetime.now().year, month, day)
    return datetime_obj


def format_df_dates(df: pd.DataFrame) -> pd.DataFrame:
    program_submitted_idx = cast(int, df.columns.get_loc("Program Submitted"))
    df.insert(program_submitted_idx + 1, "Program Submitted Text", "")

    program_executed_idx = cast(int, df.columns.get_loc("Program Executed"))
    df.insert(program_executed_idx + 1, "Program Executed Text", "")

    broker_executed_idx = cast(int, df.columns.get_loc("Broker Executed"))
    df.insert(broker_executed_idx + 1, "Broker Executed Text", "")

    df["Program Submitted"] = pd.to_datetime(df["Program Submitted"], errors="coerce")
    df["Program Executed"] = pd.to_datetime(df["Program Executed"], errors="coerce")
    df["Broker Executed"] = pd.to_datetime(
        df["Broker Executed"], format="%X", errors="coerce"
    )

    df.loc[df["Program Submitted"].notna(), "Program Submitted Text"] = df.loc[
        df["Program Submitted"].notna(), "Program Submitted"
    ].dt.strftime("%X %p")
    df.loc[df["Program Executed"].notna(), "Program Executed Text"] = df.loc[
        df["Program Executed"].notna(), "Program Executed"
    ].dt.strftime("%X %p")
    df.loc[df["Broker Executed"].notna(), "Broker Executed Text"] = df.loc[
        df["Broker Executed"].notna(), "Broker Executed"
    ].dt.strftime("%X %p")

    df["Date"] = df["Date"].dt.strftime("%m/%d/%Y")
    df["Program Submitted"] = df["Program Submitted"].dt.strftime("%X:%f")
    df["Program Executed"] = df["Program Executed"].dt.strftime("%X:%f")
    df["Broker Executed"] = df["Broker Executed"].dt.strftime("%X")
    df["Action"] = df["Action"].map({"Buy": 1, "Sell": -1})

    return df


def combine_ibkr_data(df: pd.DataFrame, ib_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if ib_df is not None:
        logger.info(f"Combining IBKR")
        df_if = df[df["Broker"] == "IF"]
        res = pd.merge(
            df_if,
            ib_df,
            on=["Symbol", "Action"],
            how="outer",
            suffixes=(None, "_y"),
        )
        res["Broker Executed"] = res["Broker Executed_y"]
        res["Price"] = res["Price_y"]
        res["Dollar Amt"] = res["Dollar Amt_y"]
        res["Size"] = res["Size_y"]
        res["Broker"] = "IF"
        res["Split"] = res["Split_y"]
        res = res.drop(
            columns=[
                "Size_y",
                "Price_y",
                "Broker Executed_y",
                "Dollar Amt_y",
                "Split_y",
                "Expiration",
                "Strike",
                "Option Type",
            ]
        )
        res = res[res["Broker Executed"].notna()]
        df = df.drop(df_if.index)
        df = pd.concat([df, res], axis=0, ignore_index=True)
        logger.info("Done IBKR")
    return df


def combine_schwab_data(
    df: pd.DataFrame, sb_df: Optional[pd.DataFrame], option: bool = False
) -> pd.DataFrame:
    if sb_df is not None:
        logger.info("Combining Schwab")
        df_sb = df[df["Broker"] == "SB"]
        if option:
            sb_df_options = sb_df[sb_df["Option Type"].notna()]
            res = pd.merge(
                df_sb,
                sb_df_options,
                on=["Symbol", "Action"],
                how="outer",
                suffixes=(None, "_y"),
            )
            res["Price"] = res["Price_y"]
            res["Dollar Amt"] = res["Dollar Amt_y"]
            res["Expiration"] = res["Expiration_y"]
            res["Strike"] = res["Strike_y"]
            res["Option Type"] = res["Option Type_y"]
            res = res.drop(
                columns=[
                    "Price_y",
                    "Size",
                    "Date_y",
                    "Dollar Amt_y",
                    "Expiration_y",
                    "Strike_y",
                    "Option Type_y",
                ]
            )
        else:
            sb_df_equities = sb_df[sb_df["Option Type"].isna()]
            res = pd.merge(
                df_sb,
                sb_df_equities,
                on=["Symbol", "Action"],
                how="outer",
                suffixes=(None, "_y"),
            )
            res["Price"] = res["Price_y"]
            res["Dollar Amt"] = res["Dollar Amt_y"]
            res["Size"] = res["Size_y"]
            res = res.drop(
                columns=[
                    "Size_y",
                    "Price_y",
                    "Dollar Amt_y",
                    "Expiration",
                    "Strike",
                    "Option Type",
                    "Date_y",
                ]
            )

        res = res[res["Dollar Amt"].notna()]
        res["Broker"] = "SB"
        df = df.drop(df_sb.index)
        df = pd.concat([df, res], axis=0, ignore_index=True)
        logger.info("Done Schwab")
    return df


def combine_robinhood_data(df: pd.DataFrame, option: bool = False) -> pd.DataFrame:
    logger.info("Combining Robinhood")

    df.loc[df["Broker"] == "RH"] = df.loc[df["Broker"] == "RH"].apply(
        get_robinhood_data if not option else get_robinhood_option_data, axis=1
    )
    if option:
        df["Expiration"] = pd.to_datetime(df["Expiration"], format="%Y-%m-%d")
    logger.info("Done Robinhood")
    return df


def combine_fidelity_data(
    df: pd.DataFrame, fd_df: Optional[pd.DataFrame], option: bool = False
) -> pd.DataFrame:
    logger.info("Combining Fidelity")
    if fd_df is not None:
        df_fd = df.loc[df["Broker"] == "FD"]
        if option:
            fd_df_equities = fd_df[fd_df["Option Type"].notna()]
            res = pd.merge_asof(
                df_fd,
                fd_df_equities,
                left_on="Program Executed",
                right_on="Broker Executed",
                by=["Symbol", "Action"],
                direction="nearest",
                suffixes=(None, "_y"),
            )
            res[
                [
                    "Price",
                    "Broker Executed",
                    "Dollar Amt",
                    "Strike",
                    "Expiration",
                    "Option Type",
                ]
            ] = res[
                [
                    "Price_y",
                    "Broker Executed_y",
                    "Dollar Amt_y",
                    "Strike_y",
                    "Expiration_y",
                    "Option Type_y",
                ]
            ]
            res = res.drop(
                columns=[
                    "Price_y",
                    "Size",
                    "Date_y",
                    "Dollar Amt_y",
                    "Expiration_y",
                    "Strike_y",
                    "Option Type_y",
                    "Identifier",
                    "Split",
                    "Broker Executed_y",
                ]
            )
        else:
            fd_df_equities = fd_df[(fd_df["Option Type"].isna())]
            fd_df_equities_no_split = fd_df_equities[fd_df_equities["Split"] == False]
            res = pd.merge(
                df_fd,
                fd_df_equities_no_split,
                on=["Symbol", "Action", "Size"],
                how="outer",
                suffixes=(None, "_y"),
            )
            res[["Broker Executed", "Price", "Dollar Amt", "Split"]] = res[
                ["Broker Executed_y", "Price_y", "Dollar Amt_y", "Split_y"]
            ]
            res = res.drop(
                columns=[
                    "Broker Executed_y",
                    "Price_y",
                    "Dollar Amt_y",
                    "Split_y",
                    "Expiration",
                    "Strike",
                    "Option Type",
                    "Identifier",
                    "Date_y",
                ]
            )
            fd_df_equities_split = fd_df_equities[fd_df_equities["Split"] == True]
            splits = pd.DataFrame(columns=df_fd.columns)
            indices = []
            for _, row in fd_df_equities_split.iterrows():
                report_row = df_fd[
                    (df_fd["Symbol"] == row["Symbol"])
                    & (df_fd["Action"] == row["Action"])
                    & (df_fd["Size"] >= 1)
                ].copy()
                if report_row.shape[0] != 0:
                    indices.append(report_row.index[0])
                    report_row[
                        ["Broker Executed", "Price", "Dollar Amt", "Size", "Split"]
                    ] = row[["Broker Executed", "Price", "Dollar Amt", "Size", "Split"]]
                    splits = pd.concat([splits, report_row], axis=0, ignore_index=True)
                else:
                    data = (
                        df_fd[(df_fd["Action"] == row["Action"]) & (df_fd["Size"] >= 1)]
                        .iloc[[0]]
                        .copy()
                    )
                    data[:] = np.nan
                    cols = [
                        "Broker Executed",
                        "Price",
                        "Dollar Amt",
                        "Size",
                        "Split",
                        "Symbol",
                        "Action",
                    ]
                    data[cols] = row[cols]
                    data["Order Type"] = "Market"
                    splits = pd.concat([splits, data], axis=0, ignore_index=True)

            res = pd.concat([res, splits], axis=0, ignore_index=True)

        res = res[res["Dollar Amt"].notna()]
        res["Broker"] = "FD"
        df = df.drop(df_fd.index)
        df = pd.concat([df, res], axis=0, ignore_index=True)
        logger.info("Done Fidelity")
    return df


def perform_equity_analysis(df: pd.DataFrame) -> pd.DataFrame:
    price_idx = cast(int, df.columns.get_loc("Price"))
    df.insert(price_idx + 1, "Rounded Price - Price", "")
    df["Rounded Price - Price"] = vectorized_calculate_rounded_price(
        df["Price"].to_numpy(dtype="float64")
    )

    # bid - highest buyer is willing to buy
    # ask - lowest seller is willing to sell

    # =IF(OR(AND(J3=1,L3<Z3),AND(L3>Y3,J3=-1)),1,0)
    df.insert(price_idx + 2, "PriceImprovement", "")
    df.loc[df["Price"].notna(), "PriceImprovement"] = df.loc[
        df["Price"].notna(), ["Action", "Price", "Pre Bid", "Pre Ask"]
    ].apply(optimized_calculate_price_improvement, axis=1)

    df.insert(price_idx + 3, "Subpenny", "")
    df.insert(price_idx + 4, "FractionalPIno5", "")
    df.loc[df["Rounded Price - Price"].notna(), ["Subpenny", "FractionalPIno5"]] = (
        df.loc[df["Rounded Price - Price"].notna(), "Rounded Price - Price"].apply(
            optimized_calculate_subpenny_and_fractionalpino5
        )
    )

    df.insert(price_idx + 5, "BJZZ Flag", "")
    df.loc[df["Rounded Price - Price"].notna(), "BJZZ Flag"] = df.loc[
        df["Rounded Price - Price"].notna(), "Rounded Price - Price"
    ].apply(optimized_calculate_BJZZ_flag)

    df.insert(price_idx + 6, "Correct", "")
    df.insert(price_idx + 7, "Wrong", "")
    df.loc[df["Rounded Price - Price"].notna(), ["Correct", "Wrong"]] = df.loc[
        df["Rounded Price - Price"].notna(),
        ["Action", "Rounded Price - Price", "BJZZ Flag"],
    ].apply(optimized_calculate_correct_and_wrong, axis=1, result_type="expand")

    df.insert(price_idx + 8, "Categories", "")
    df.loc[df["Rounded Price - Price"].notna(), "Categories"] = df.loc[
        df["Rounded Price - Price"].notna(),
        ["Rounded Price - Price", "FractionalPIno5", "Correct"],
    ].apply(optimized_calculate_categories, axis=1)

    df.insert(price_idx + 9, "BJZZ", "")
    df.loc[df["Rounded Price - Price"].notna(), "BJZZ"] = df.loc[
        df["Rounded Price - Price"].notna(), "Rounded Price - Price"
    ].apply(optimized_calculate_bjzz)

    post_vol_idx = cast(int, df.columns.get_loc("Post Volume"))
    df.insert(post_vol_idx + 1, "First", 0)
    df.insert(post_vol_idx + 2, "BigTrade", 0)
    df.loc[(df["Size"] == 100) & (df["Broker"] == "FD"), ["BigTrade"]] = 1
    df.insert(post_vol_idx + 3, "TradeID", "")

    df["TradeID"] = (
        df["Date"].dt.year.astype(str)
        + df["Date"].dt.month.map("{:02}".format).astype(str)
        + df["Date"].dt.day.astype(str)
        + df["Symbol"]
        + np.where(df["BigTrade"].to_numpy(dtype="int64") == 0, "0100", "100")
    )

    split_idx = cast(int, df.columns.get_loc("Split"))
    df.insert(split_idx + 1, "BidAskSpread", "")
    df.insert(split_idx + 2, "TradeLocation", "")

    df["BidAskSpread"] = df["Pre Ask"] - df["Pre Bid"]
    df["BidAskSpread"] = pd.to_numeric(df["BidAskSpread"])
    df["BidAskSpread"] = df["BidAskSpread"].round(4)

    df["Price"] = pd.to_numeric(df["Price"])
    df["Pre Bid"] = pd.to_numeric(df["Pre Bid"])
    df["TradeLocation"] = ((df["Price"] - df["Pre Bid"]) / df["BidAskSpread"]).round(4)

    # time formatting -> add text columns next to numeric time
    df = format_df_dates(df)
    df["Split"] = df["Split"].map({True: 1, False: 0})
    return df


def perform_option_analysis(df: pd.DataFrame) -> pd.DataFrame:
    df = format_df_dates(df)
    # df["Expiration"] = pd.to_datetime(df["Expiration"], format="%Y-%m-%d")
    # df["Expiration"] = df["Expiration"].dt.strftime("%m/%d/%Y")
    return df


if __name__ == "__main__":
    pass
