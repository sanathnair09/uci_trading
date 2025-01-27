import ujson as json  # type: ignore[import-untyped]
from brokers import BASE_PATH

class TwentyFourHourManager:

    def __init__(self):
        self._24_info_path = BASE_PATH / "twenty_four_hour_info.json"

    def set(self, key: str, value) -> None:
        
        with open(self._24_info_path, "r") as file:
            data = json.load(file)
            data[key] = value

        with open(self._24_info_path, "w") as file:
            json.dump(data, file, indent=4)

    def get(self, key: str):
        
        with open(self._24_info_path, "r") as file:
            return json.load(file)[key]

    
