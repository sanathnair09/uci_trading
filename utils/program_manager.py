import ujson as json
from pathlib import Path
import sys
from datetime import datetime
import random
from typing import Any, Union

from loguru import logger

from brokers import BASE_PATH

# fmt: off
SYM_LIST = [
    "RAPT", "DHIL", "TACT", "RM", "CAPR", "PANW", "HEAR", "IMNM", "DOUG", "IMAQ",
    "CRS", "CDNA", "CTMX", "SIX", "ICAD", "VKTX", "MODN", "CHCI", "FHN", "RBCAA",
    "PFMT", "QUAD", "NNBR", "TSLA", "LASE", "APLS", "BYNO", "SCKT", "AVO", "TRIP",
    "MMI", "EDUC", "ICCC", "PTLO", "KNDI", "GS", "OXM", "ANIP", "BCC",  # removed "WH" 2/15/24
    "NEON", "NTAP", "PXLW", "NOV", "AAPL", "HEI", "AWR", "CFFS", "OLMA", "MCW",
    "XOM", "GOOG", "SPY", "CVCO", "AMP", "LXRX", "NOTV", "COSM", "MSFT", "VNDA",
    "NXTC", "EW", "ADRT", "CAL", "GIS", "NVDA", "GLT", "GBCI", "RCKT", "HONE",
    "AMPS", "OKE", "ALXO", "PFIS", "WMPN", "SXI", "CVLT", "WRB", "FRBA", "DCTH",
    "BAC", "ROOT", "JNPR", "UNF", "TRV", "AMTB", "TDG", "V", "ASB", "MSI",
    "PACK", "CPK", "OPRT", "F", "BND", "ALB", "GO", "SHLS", "AMTX", "GRWG",
    "APT", "RAVE", "WTFC", "CVLY", "WBS", "TCRX", "RWOD", "NEPH", "GWRE", "ARC",
    "AGX", "ODFL", "QQQ", "INBX", "SCHL", "BATL", "ZUMZ", "AMC", "PRTH", "MKTX",
    "SSNC", "AAP", "RAMP", "AGL", "FFIV", "CELC", "LUNG", "UBER", "PROV", "RDI", # removed NSTB 2/8/24
    "PVH", "TSVT", "BBSI",  "PLPC", "IFF", "INZY", "CSX",  "AMZN", "EWTX",
    "BV", "POWW", "CATO", "INAQ",
]

SYM_LIST_LEN = len(SYM_LIST)

REPORT_COLUMNS = [
    'Date', 'Program Submitted', 'Program Executed', 'Broker Executed', 'Symbol',
    'Broker', 'Action', 'Size', 'Price', 'Dollar Amt', 'Pre Quote', 'Post Quote',
    'Pre Bid', 'Pre Ask', 'Post Bid', 'Post Ask', 'Pre Volume', 'Post Volume',
    'Order Type', 'Split', 'Order ID', 'Activity ID'
    ]

OPTION_REPORT_COLUMNS = [
    'Date', 'Program Submitted', 'Program Executed', 'Broker Executed', 'Symbol',
    'Strike','Option Type', 'Expiration', 'Trade Size', 'Broker', 'Action', 'Price',
    'Pre Quote', 'Post Quote', 'Pre Bid', 'Pre Ask', 'Post Bid', 'Post Ask', 'Pre Volume',
    'Post Volume', "Pre Volatility", "Post Volatility", "Pre Delta", "Post Delta", "Pre Theta",
    "Post Theta", "Pre Gamma", "Post Gamma", "Pre Vega", "Post Vega", "Pre Rho", "Post Rho",
    "Pre Underlying Price", "Post Underlying Price", "Pre In The Money", "Post In The Money",
    'Order Type', "Venue", 'Order ID', 'Activity ID'
    ]


# fmt: on
class ProgramManager:
    def __init__(self, base_path: Path = BASE_PATH, *, enable_stdout: bool = False):
        self._enable_stdout = enable_stdout

        self._program_info_path = base_path / "program_info.json"
        date = datetime.now().strftime("%m_%d")
        self._log_path = base_path / f"logs/log_{date}.log"
        self.report_file = base_path / f"reports/original/report_{date}.csv"
        self.option_report_file = (
            base_path / f"reports/original/option_report_{date}.csv"
        )

        self._default_values = {
            "DATE": datetime.now().strftime("%x"),
            # if creating a new file choose a random starting point
            "PREVIOUS_STOCK_NAME": random.choice(SYM_LIST),
            "STATUS": "Buy",
            "CURRENTLY_TRADING_STOCKS": [],
            "CURRENTLY_TRADING_OPTION": [],
            "CURRENT_BIG_TRADES": [],
            "CURRENT_FRACTIONAL_TRADES": [],
            "COMPLETED": 0,
            "COMPLETED_OPTIONS": 0,
        }

        self._init_logging()
        self._initialize_files()

    def _initialize_files(self) -> None:
        if not self._program_info_path.exists():
            logger.info("Creating program file...")
            with open(self._program_info_path, "w+") as file:
                json.dump(self._default_values, file, indent=4)
            logger.info("Finished creating program file...")
        else:
            with open(self._program_info_path, "r+") as file:
                data = json.load(file)
                if data.keys() != self._default_values.keys():
                    logger.info("Updating program file...")
                    new_data = self._default_values | data
                    file.truncate(0)  # clears file
                    file.seek(0)  # moves pointer to beginning
                    json.dump(new_data, file, indent=4)
                    logger.info("Finished updating program file...")

        def create_file(file: Path, report_columns: list[str], msg: str) -> None:
            if not file.exists():
                logger.info(f"Creating {msg} file...")
                with open(file, "w") as f:
                    f.write(",".join(report_columns) + "\n")
                    logger.info(f"Finished creating {msg} file...")

        create_file(self.report_file, REPORT_COLUMNS, "report")
        create_file(self.option_report_file, OPTION_REPORT_COLUMNS, "option report")

    def _init_logging(self) -> None:
        logger.remove()
        sep = "<r>|</r>"
        time = "<g>{time:hh:mm:ss}</g>"
        level = "<level>{level}</level>"
        traceback = "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        message = "<level>{message}</level>"
        if self._enable_stdout:
            logger.add(
                sys.stdout,
                format=f"{time} {sep} {level} {sep} {traceback} {sep} {message}",
            )
        logger.add(
            self._log_path,
            format=f"{time} {sep} {level} {sep} {traceback} {sep} {message}",
            enqueue=True,
        )

    def _check_valid_key(self, key: str) -> None:
        if key not in self._default_values:
            raise KeyError(
                f"{key} not a valid key: {list(self._default_values.keys())}"
            )

    def update_program_data(self, key: str, value: Union[str, list, int]) -> None:
        self._check_valid_key(key)
        with open(self._program_info_path, "r") as file:
            data = json.load(file)
            data[key] = value

        with open(self._program_info_path, "w") as file:
            json.dump(data, file, indent=4)

    def get_program_data(self, key: str) -> Any:
        self._check_valid_key(key)
        with open(self._program_info_path, "r") as file:
            return json.load(file)[key]


if __name__ == "__main__":
    manager = ProgramManager()
