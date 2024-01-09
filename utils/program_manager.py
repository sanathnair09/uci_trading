import json
import sys
from datetime import datetime
import random
from typing import Any

from loguru import logger

from brokers import BASE_PATH


SYM_LIST = [
    "RAPT", "DHIL", "TACT", "RM", "CAPR", "PANW", "HEAR", "IMNM", "DOUG", "IMAQ",
    "CRS", "CDNA", "CTMX", "SIX", "ICAD", "GEVO", "MODN", "CHCI", "FHN", "RBCAA"
    "PFMT", "QUAD", "NNBR", "TSLA", "LASE", "APLS", "BYNO", "SCKT", "AVO", "TRIP",
    "MMI", "EDUC", "ICCC", "PTLO", "KNDI", "GS", "OXM", "ANIP", "BCC", "WH",
    "NEON", "NTAP", "PXLW", "NOV", "AAPL", "HEI", "AWR", "CFFS", "OLMA", "MCW",
    "XOM", "GOOG", "SPY", "CVCO", "AMP", "LXRX", "NOTV", "COSM", "MSFT", "VNDA",
    "NXTC", "EW", "ADRT", "CAL", "GIS", "NVDA", "GLT", "GBCI", "RCKT", "HONE",
    "OPK", "OKE", "ALXO", "PFIS", "WMPN", "SXI", "CVLT", "WRB", "FRBA", "DCTH",
    "BAC", "ROOT", "JNPR", "UNF", "TRV", "AMTB", "TDG", "V", "ASB", "MSI",
    "PACK", "CPK", "OPRT", "F", "BND", "ALB", "GO", "SHLS", "AMTX", "GRWG",
    "APT", "RAVE", "WTFC", "CVLY", "WBS", "TCRX", "RWOD", "NEPH", "GWRE", "ARC",
    "AGX", "ODFL", "QQQ", "INBX", "SCHL", "BATL", "ZUMZ", "AMC", "PRTH", "W",
    "SSNC", "AAP", "RAMP", "AGL", "FFIV", "CELC", "LUNG", "UBER", "PROV", "RDI",
    "PVH", "TSVT", "BBSI", "NSTB", "PLPC", "IFF", "INZY", "CSX",  "AMZN", "EWTX",
    "BV", "POWW", "CATO", "INAQ",
]

SYM_LIST_LEN = len(SYM_LIST)

REPORT_COLUMNS = ['Date', 'Program Submitted', 'Program Executed', 'Broker Executed', 'Symbol',
                  'Broker', 'Action', 'Size', 'Price', 'Dollar Amt', 'Pre Quote', 'Post Quote',
                  'Pre Bid', 'Pre Ask', 'Post Bid', 'Post Ask', 'Pre Volume', 'Post Volume',
                  'Order Type', 'Split', 'Order ID', 'Activity ID']


class ProgramManager:
    def __init__(self, *, enable_stdout = False):
        self._enable_stdout = enable_stdout

        self._program_info_path = BASE_PATH / "program_info.json"
        self._log_path = BASE_PATH / f"logs/log_{datetime.now().strftime('%m_%d')}.log"
        self._report_file = BASE_PATH / f"reports/original/report_{datetime.now().strftime('%m_%d')}.csv"

        self._default_values = {
            "DATE": datetime.now().strftime("%x"),
            "PREVIOUS_STOCK_NAME": random.choice(SYM_LIST), # if creating a new file choose a random starting point
            "STATUS": "Buy",
            "CURRENTLY_TRADING_STOCKS": [],
            "CURRENT_BIG_TRADES": [],
            "CURRENT_FRACTIONAL_TRADES": [],
            "COMPLETED": 0
        }

        self._initialize_files()
        self._init_logging()

    def _initialize_files(self):
        if not self._program_info_path.exists():
            print("Creating program file...")
            with open(self._program_info_path, "w") as file:
                json.dump(self._default_values, file, indent = 4)
            print("Finished creating program file...")
        else:
            with open(self._program_info_path, "r+") as file:
                data = json.load(file)
                if data.keys() != self._default_values.keys():
                    print("Updating program file...")
                    new_data = self._default_values | data
                    file.truncate(0)  # clears file
                    file.seek(0) # moves pointer to beginning
                    json.dump(new_data, file, indent = 4)
                    print("Finished updating program file...")

        if not self._report_file.exists():
            print("Creating report file...")
            with open(self._report_file, "w") as file:
                file.write(",".join(REPORT_COLUMNS) + "\n")
                print("Finished creating report file...")

    def _init_logging(self):
        logger.remove()
        sep = "<r>|</r>"
        time = "<g>{time:hh:mm:ss}</g>"
        level = "<level>{level}</level>"
        traceback = "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        message = "<level>{message}</level>"
        if self._enable_stdout:
            logger.add(sys.stdout,
                       format = f"{time} {sep} {level} {sep} {traceback} {sep} {message}")
        logger.add(self._log_path,
                   format = f"{time} {sep} {level} {sep} {traceback} {sep} {message}",
                   enqueue = True)

    def _check_valid_key(self, key):
        if key not in self._default_values:
            raise KeyError(f"{key} not a valid key: {list(self._default_values.keys())}")

    def update_program_data(self, key: str, value: Any):
        self._check_valid_key(key)
        with open(self._program_info_path, "r") as file:
            data = json.load(file)
            data[key] = value

        with open(self._program_info_path, "w") as file:
            json.dump(data, file, indent = 4)

    def get_program_data(self, key):
        self._check_valid_key(key)
        with open(self._program_info_path, "r") as file:
            return json.load(file)[key]

    def report_file(self):
        return self._report_file


if __name__ == '__main__':
    manager = ProgramManager()