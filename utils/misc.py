import json
from typing import Union
import pandas as pd
import robin_stocks.robinhood as rh


def repeat_on_fail(times: int = 5, default_return = False) -> any:
    def _repeat(func):
        def wrapper(*args, **kwargs):
            _times = times
            while _times != 0:
                try:
                    res = func(*args, **kwargs)
                    return res
                except Exception as e:
                    if e:
                        print(e)
                    _times -= 1
            return default_return

        return wrapper

    return _repeat


def repeat(times: int = 5) -> any:
    def _repeat(func):
        def wrapper(*args, **kwargs):
            _times = times
            while _times != 0:
                func(*args, **kwargs)
                _times -= 1

        return wrapper

    return _repeat


def calculate_num_stocks_to_buy(dollar_amt: float, stock_price: float):
    return max(1, round(dollar_amt / stock_price))


def update_program_data(file_path: str, key: str,
                        value: Union[
                            str, int, any],
                        is_list: bool = False):
    with open(file_path, "r") as file:
        data = json.load(file)

    if not is_list:
        data[key] = value
    else:
        data[key].append(value)

    with open(file_path, "w") as file:
        json.dump(data, file, indent = 4)


def reset_program_data(file_path, default: list[tuple[str, any]]):
    with open(file_path, "r") as file:
        data = json.load(file)

    for key, value in default:
        data[key] = value

    with open(file_path, "w") as file:
        json.dump(data, file, indent = 4)


def get_program_data(file_path: str, key: str):
    with open(file_path, "r") as file:
        return json.load(file)[key]


def get_broker_data(orderId):
    order_data = rh.get_stock_order_info(orderId)
    try:
        return (
            order_data["executions"][0]["timestamp"],
            order_data["average_price"],
            order_data["cumulative_quantity"],
            order_data["total_notional"]["amount"],
        )
    except:
        return (
            order_data["last_transaction_at"],
            order_data["average_price"],
            order_data["cumulative_quantity"],
            order_data["total_notional"]["amount"],
        )


def cleanup_report(report_file: str):
    df = pd.read_csv(report_file)
    df = df.fillna('')
    df = df.replace(-1, '')


    # for index, row in df.iterrows():
    #     if row['Broker'] in ['Robinhood', 'RH']:
    #         broker_data = get_broker_data(row['Order ID'])
    #         df.at[index, 'Broker Executed'] = broker_data[0]
    #         df.at[index, 'Price'] = broker_data[1]
    #         df.at[index, 'No. of Shares'] = broker_data[2]
    #         df.at[index, 'Dollar Amt'] = broker_data[3]

    df.to_csv(f"../reports/{report_file}_filtered.csv")


if __name__ == '__main__':
    # cleanup_report("../reports/report_06_27.csv")
    pass