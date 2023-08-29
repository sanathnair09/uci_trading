import os
from pathlib import Path

from dotenv import load_dotenv

BASE_PATH = Path("/Users/sanathnair/Developer/trading") # FIXME: relative path name

file_path = BASE_PATH / ".env"
load_dotenv(file_path)

RH_LOGIN = os.getenv("RH_LOGIN")
RH_PASSWORD = os.getenv("RH_PASSWORD")

TD_KEY = os.getenv("TD_KEY")
TD_URI = os.getenv("TD_URI")
TD_TOKEN_PATH = os.getenv("TD_TOKEN_PATH")
TD_ACC_NUM = os.getenv("TD_ACC_NUM")

ETRADE_CONSUMER_KEY = os.getenv("ETRADE_CONSUMER_KEY")
ETRADE_CONSUMER_SECRET = os.getenv("ETRADE_CONSUMER_SECRET")
ETRADE_LOGIN = os.getenv("ETRADE_LOGIN")
ETRADE_PASSWORD = os.getenv("ETRADE_PASSWORD")
ETRADE_ACCOUNT_ID = os.getenv("ETRADE_ACCOUNT_ID")

ETRADE2_CONSUMER_KEY = os.getenv("ETRADE2_CONSUMER_KEY")
ETRADE2_CONSUMER_SECRET = os.getenv("ETRADE2_CONSUMER_SECRET")
ETRADE2_LOGIN = os.getenv("ETRADE2_LOGIN")
ETRADE2_PASSWORD = os.getenv("ETRADE2_PASSWORD")
ETRADE2_ACCOUNT_ID = os.getenv("ETRADE2_ACCOUNT_ID")

SCHWAB_LOGIN = os.getenv("SCHWAB_LOGIN")
SCHWAB_PASSWORD = os.getenv("SCHWAB_PASSWORD")

FIDELITY_LOGIN = os.getenv("FIDELITY_LOGIN")
FIDELITY_PASSWORD = os.getenv("FIDELITY_PASSWORD")

IBKR_LOGIN = os.getenv("IBKR_LOGIN")
IBKR_PASSWORD = os.getenv("IBKR_PASSWORD")

from .td_ameritrade import TDAmeritrade
from .robinhood import Robinhood
from .etrade import ETrade
from .schwab import Schwab
from .fidelity import Fidelity
from .ibkr import IBKR
