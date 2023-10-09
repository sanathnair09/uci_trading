import json
import sys
from datetime import datetime
from typing import Any

from loguru import logger

from brokers import BASE_PATH


# SYM_LIST = [
#     'UNF', 'WH', 'ODFL', 'NOTV', 'GRWG', 'RAPT', 'WTFC', 'CAPR', 'XOM', 'OPRT', 'BYN',  # 10
#     'SHLS', 'AGL', 'BATL', 'HEAR', 'SCHL', 'IFF', 'EDUC', 'AAP', 'PANW',  # 20
#     'TRV', 'AMTX', 'HONE', 'AMTB', 'CVCO', 'CAL', 'GLT', 'NVDA', 'HEI', 'DUNE',  # 30
#     'OKE', 'BCC', 'BV', 'PRTH', 'NOV', 'ROOT', 'TSLA', 'MICS', 'PVH', 'CSX',  # 40
#     'CTMX', 'BYNO', 'NXTC', 'DTOC', 'OLMA', 'POWW', 'INBX', 'W', 'PCYG', 'GO',  # 50 NGC
#     'ALXO', 'ZUMZ', 'ENER', 'ADRT', 'CRS', 'WRB', 'RAMP', 'CVLY', 'IMNM', 'EWTX',  # 60 CELC
#     'V', 'EBIX', 'INZY', 'BAC', 'DISH', 'PFMT', 'NNBR', 'MCW', 'RDI', 'DWAC',  # 70
#     'CVLT', 'RAVE', 'LASE', 'OXM', 'APT', 'ASB', 'MSI', 'SNSE', 'ANIP', 'BBSI',  # 80 TETC
#     'VNDA', 'TDG', 'ICAD', 'LXRX', 'EW', 'AMP', 'MODN', 'NRG', 'FRBA', 'GIS',  # 90
#     'SCKT', 'AMC', 'KNDI', 'ATRA', 'KVSA', 'AVO', 'SMAP', 'PACK', 'NTAP', 'PLPC',  # 100 AAWW
#     'GOOG', 'RM', 'APLS', 'ICCC', 'PROV', 'GEVO', 'RWOD', 'WMPN', 'AWR', 'DCTH',  # 110
#     'SXI', 'DHIL', 'CDNA', 'MMI', 'YHGJ', 'GBCI', 'AAPL', 'SSNC', 'TCRX', 'OPK',  # 120
#     'FFIV', 'AGX', 'PTLO', 'LUNG', 'CPK', 'TACT', 'SIX', 'GS', 'PXLW', 'GWRE',  # 130 KNBE
#     'WBS', 'ALB', 'CCVI'  # 133 'BYN' moved
# ]
SYM_LIST = [
    "AMTB", "AMTX", "BCC", "BV", "CVCO", "DUNE", "GLT", "HEI", "HONE", "NOV", "NVDA",
    "PRTH", "TRV", "WRB", "DCTH", "KVSA", "PLPC", "PCYG", "ENER", "XOM", "W", "OXM",
    "SSNC", "NXTC", "BYN", "GBCI", "GS", "AAPL", "TDG", "AVO", "ASB", "DISH", "BBSI",
    "RAMP", "V", "WMPN", "APT", "CRS", "AMC", "CPK", "DWAC", "KNDI", "IMNM", "ICAD",
    "SIX", "CVLY", "ANIP", "APLS", "UNF", "CDNA", "HEAR", "ROOT", "MSI", "GRWG", "MICS",
    "PTLO", "LXRX", "TCRX", "RWOD", "EW", "NTAP", "SMAP", "GO", "PANW", "POWW", "ATRA",
    "MODN", "PXLW", "AGL", "EDUC", "ZUMZ", "FFIV", "WH", "GOOG", "WTFC", "BYNO", "PVH",
    "PFMT", "AWR", "FRBA", "GIS", "RAPT", "CSX", "DTOC", "SXI", "ICCC", "LUNG", "ADRT",
    "VNDA", "CAPR", "PACK", "TSLA"
]

STOCK_LIST_LEN = len(SYM_LIST)

REPORT_COLUMNS = ['Date', 'Program Submitted', 'Program Executed', 'Broker Executed', 'Symbol',
                  'Broker', 'Action', 'Size', 'Price', 'Dollar Amt', 'Pre Quote', 'Post Quote',
                  'Pre Bid', 'Pre Ask', 'Post Bid', 'Post Ask', 'Pre Volume', 'Post Volume',
                  'Order Type', 'Split', 'Order ID', 'Activity ID']


class ProgramManager:
    def __init__(self, *, enable_stdout = False):
        self._enable_stdout = enable_stdout

        self._program_info_path = BASE_PATH / "previous_program_info.json"
        self._log_path = BASE_PATH / f"logs/log_{datetime.now().strftime('%m_%d')}.log"
        self._report_file = BASE_PATH / f"reports/original/report_{datetime.now().strftime('%m_%d')}.csv"

        self._default_values = {
            "PREVIOUS_STOCK_NAME": SYM_LIST[0],
            "STATUS": "Buy",
            "CURRENTLY_TRADING_STOCKS": [],
            "CURRENT_BIG_TRADES": [],
            "CURRENT_FRACTIONAL_TRADES": [],
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