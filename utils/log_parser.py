from math import log
from pathlib import Path

import pandas as pd


def parse_log(log_file: Path):
    with log_file.open("r") as file:
        data = []
        for line in file:
            if "Error buying" in line or "Error selling" in line:
                parts = line.split("|")
                if "perform" not in parts[2]:
                    continue
                msg = parts[3].split(" ")
                time = parts[0]
                broker = msg[1]
                if "option" in parts[2]:
                    data.append([time, broker, msg[4], msg[3], "Option"])
                else:
                    data.append([time, broker, msg[5][1:-1], msg[3], "Stock"])
        df = pd.DataFrame(
            data,
            columns=["time", "broker", "symbol", "action", "type"],
        )
        df["action"] = df["action"].map({"buying": 1, "selling": -1})
        output_file = log_file.parent / "processed" / log_file.name
        df.to_csv(output_file.with_suffix(".csv"), index=False)


if __name__ == "__main__":
    parse_log(Path(f"/Users/sanathnair/Developer/trading/logs/log_04_03.log"))
