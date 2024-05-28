import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, cast

import numpy as np
import pandas as pd
from loguru import logger

from brokers import BASE_PATH
from brokers.etrade import ETrade
from brokers.robinhood import Robinhood
from utils.broker import Broker
from utils.report.report import BrokerNames
from utils.report.report_utils import (
    convert_int64_utc_to_pst,
    create_datetime_from_string,
    get_fidelity_report,
    get_ibkr_report,
    get_schwab_report,
    combine_ibkr_data,
    combine_schwab_data,
    combine_fidelity_data,
    combine_robinhood_data,
    perform_equity_analysis,
    perform_option_analysis,
    check_file_existence,
)


class PostProcessing:
    def __init__(self, out_file_ver: int = 0) -> None:
        self._output_file_version = "" if out_file_ver == 0 else out_file_ver
        self._brokers: dict[str, Broker] = {}
        self._login()

    def _login(self) -> None:
        Robinhood.login_custom(account="RH2")
        self._brokers = {
            "E2": ETrade(Path(""), BrokerNames.E2),
        }
        for broker in self._brokers.values():
            broker.login()

        logger.info("Finished logging in...")

    def _read_report(self, report_file: str, option: bool = False) -> pd.DataFrame:
        df = pd.read_csv(report_file)
        df["Date"] = pd.to_datetime(df["Date"])
        df["Program Submitted"] = pd.to_datetime(
            df["Program Submitted"], format="%X:%f"
        )
        df["Program Executed"] = pd.to_datetime(df["Program Executed"], format="%X:%f")
        df["Broker Executed"] = pd.to_datetime(
            df["Broker Executed"], format="%X", errors="coerce"
        )
        if option:
            df["Dollar Amt"] = np.nan

        return df

    def _get_broker_data(self, date: datetime) -> Sequence[Optional[pd.DataFrame]]:
        # ibkr_file = BASE_PATH / f"data/ibkr/DailyTradeReport.{date.strftime('%Y%m%d')}.html"
        ibkr_file = BASE_PATH / f"data/ibkr/ibkr_{date.strftime('%m_%d')}_new.csv"
        fidelity_file = (
            BASE_PATH / f"data/fidelity/fd_splits_{date.strftime('%m_%d')}.csv"
        )
        schwab_file = BASE_PATH / f"data/schwab/schwab_{date.strftime('%m_%d')}.csv"
        ibkr_df = (
            get_ibkr_report(ibkr_file) if check_file_existence(ibkr_file) else None
        )
        fidelity_df = (
            get_fidelity_report(fidelity_file)
            if check_file_existence(fidelity_file)
            else None
        )
        schwab_df = (
            get_schwab_report(schwab_file)
            if check_file_existence(schwab_file)
            else None
        )

        return ibkr_df, fidelity_df, schwab_df

    def _combine_etrade_data(
        self, df: pd.DataFrame, option: bool = False
    ) -> pd.DataFrame:
        logger.info("Combining Etrade")
        ets = df.loc[(df["Broker"] == "E2")].copy()
        ets["Order ID"] = ets["Order ID"].astype(int)
        df = df.drop(ets.index)
        et = cast(ETrade, self._brokers["E2"])
        new_ets = pd.DataFrame()
        for _, row in ets.iterrows():
            orderId = cast(str, row["Order ID"])
            if not option:
                etrade_df, is_split = et.get_order_data(orderId)
            else:
                etrade_df, is_split = et.get_option_order_data(orderId)

            for _, split in etrade_df.iterrows():
                row["Broker Executed"] = convert_int64_utc_to_pst(
                    cast(int, split["Broker Executed"])
                )
                row["Price"] = split["Price"]
                row["Dollar Amt"] = split["Dollar Amt"]
                if not option:
                    row["Size"] = split["Size"]
                    row["Split"] = is_split
                else:
                    row["Strike"] = split["Strike"]
                    row["Expiration"] = pd.to_datetime(
                        split["Expiration"], format="%m/%d/%Y"
                    )
                    row["Option Type"] = split["Option Type"]
                new_ets = pd.concat([new_ets, row.to_frame().T], ignore_index=False)
        logger.info("Done Etrade")
        return pd.concat([df, new_ets], ignore_index=False)

    def generate_report(self, report_file: str, option: bool = False) -> None:
        logger.info(f"Processing: {report_file}")
        start = time.perf_counter()

        formatted_date = create_datetime_from_string(report_file)
        ibkr_df, fidelity_df, schwab_df = self._get_broker_data(formatted_date)

        df = self._read_report(report_file, option)

        if not option:
            df = combine_ibkr_data(df, ibkr_df)

        df = combine_schwab_data(df, schwab_df, option)
        df = combine_fidelity_data(df, fidelity_df, option)
        df = self._combine_etrade_data(df, option)
        df = combine_robinhood_data(df, option)

        df["Date"] = formatted_date
        if not option:
            df = perform_equity_analysis(df)
            filtered_filename = (
                BASE_PATH
                / f'reports/filtered/report_{formatted_date.strftime("%m_%d")}_filtered{self._output_file_version}.csv'
            )
        else:
            df = perform_option_analysis(df)
            filtered_filename = (
                BASE_PATH
                / f'reports/filtered/option_report_{formatted_date.strftime("%m_%d")}_filtered{self._output_file_version}.csv'
            )

        df = df[df["Broker"].notna()]
        df.fillna("", inplace=True)
        df.to_csv(filtered_filename, index=False)

        end = time.perf_counter()
        logger.info("Finished")
        logger.info(f"{end - start} seconds")
        logger.info(f"Output file: {filtered_filename}")

        logger.info(f"Number of Trades: {len(df['Symbol'].unique())}\n")


if __name__ == "__main__":
    npp = PostProcessing()
    dir = Path("/Users/sanathnair/Developer/trading/reports/original")
    for file in dir.iterdir():
        if file.suffix == ".csv":
            res = (
                BASE_PATH / "reports/filtered" / Path(f"{file.name[:-4]}_filtered.csv")
            )
            if res.exists():
                continue
            if "option" in file.name:
                npp.generate_report(
                    file.as_uri(),
                    True,
                )
            else:
                npp.generate_report(
                    file.as_uri(),
                    False,
                )
    # npp.generate_report(
    #     "/Users/sanathnair/Developer/trading/reports/original/report_03_08.csv",
    #     False,
    # )
