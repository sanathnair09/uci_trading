import json
from datetime import datetime


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


def update_program_data(file_path: str, key: str, value: any, is_list: bool = False):
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


def generate_failure_log():
    with open("./previous_program_info.json", "r") as file:
        failure_logs = json.load(file)["FAILURE_LOG"]
        with open(f'./logs/log_{datetime.now().strftime("%m_%d")}.txt', "x") as output:
            json.dump(failure_logs, output, indent = 4)


def save_content_to_file(content, file_name, mode="w"):
    with open(file_name, mode) as file:
        file.write(content)