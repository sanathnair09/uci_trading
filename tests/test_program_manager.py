from datetime import datetime
import ujson as json
from pathlib import Path
import shutil

import pytest
from utils.program_manager import ProgramManager


class TestProgramManager:
    @pytest.fixture()
    def expected(self):
        return {
            "DATE": str,
            "PREVIOUS_STOCK_NAME": str,
            "STATUS": str,
            "CURRENTLY_TRADING_STOCKS": list,
            "CURRENTLY_TRADING_OPTION": list,
            "CURRENT_BIG_TRADES": list,
            "CURRENT_FRACTIONAL_TRADES": list,
            "COMPLETED": int,
            "COMPLETED_OPTIONS": int,
        }

    @pytest.fixture()
    def program_manager(self):
        curr_dir = Path(__file__).parent / "tmp"
        return curr_dir, ProgramManager(base_path=curr_dir)

    @pytest.fixture(autouse=True)
    def pre_post_script(self):
        # create tmp directory
        curr_dir = Path(__file__).parent / "tmp"
        curr_dir.mkdir(parents=True, exist_ok=True)
        (curr_dir / "logs").mkdir(parents=True, exist_ok=True)
        (curr_dir / "reports/original").mkdir(parents=True, exist_ok=True)
        yield  # let test run
        # delete all files in tmp directory
        shutil.rmtree(curr_dir)

    def test_program_manager_init_file(self, program_manager):
        curr_dir, manager = program_manager
        program_info = manager._program_info_path
        log_file = manager._log_path
        report_file = manager.report_file
        option_report_file = manager.option_report_file

        # check file names
        assert str(program_info) == f"{curr_dir}/program_info.json"
        date = datetime.now().strftime("%m_%d")
        assert str(log_file) == f"{curr_dir}/logs/log_{date}.log"
        assert str(report_file) == f"{curr_dir}/reports/original/report_{date}.csv"
        assert (
            str(option_report_file)
            == f"{curr_dir}/reports/original/option_report_{date}.csv"
        )

        # check if files exist
        assert program_info.exists()
        assert log_file.exists()
        assert report_file.exists()
        assert option_report_file.exists()

    def test_program_manager_program_info_file_content(self, program_manager, expected):
        _, manager = program_manager

        with open(manager._program_info_path, "r") as file:
            data = json.load(file)
            print(data)
            for key, value in data.items():
                print(key, value, expected[key])
                if key in expected:
                    assert type(value) == expected[key]

    def test_program_manager_update_program_info_file(self, expected):
        curr_dir = Path(__file__).parent / "tmp"

        incomplete_data = {
            "DATE": datetime.now().strftime("%x"),
            "STATUS": "Buy",
            "CURRENTLY_TRADING_STOCKS": [],
            "CURRENTLY_TRADING_OPTION": [],
            "CURRENT_BIG_TRADES": [],
            "CURRENT_FRACTIONAL_TRADES": [],
            "COMPLETED": 0,
            "COMPLETED_OPTIONS": 0,
        }
        with open(curr_dir / "program_info.json", "w+") as file:
            json.dump(incomplete_data, file, indent=4)

        manager = ProgramManager(base_path=curr_dir)

        self.test_program_manager_program_info_file_content(
            (curr_dir, manager), expected
        )

    def test_program_manager_get_valid_data(self, program_manager):
        _, manager = program_manager

        # only testing "Status", "Completed", "Completed Options"
        assert manager.get_program_data("STATUS") == "Buy"
        assert manager.get_program_data("COMPLETED") == 0
        assert manager.get_program_data("COMPLETED_OPTIONS") == 0

    def test_program_manager_get_invalid_data(self, program_manager):
        _, manager = program_manager

        with pytest.raises(KeyError) as error:
            manager.get_program_data("INVALID_KEY")

    def test_program_manager_update_data_for_valid_key(self, program_manager):
        _, manager = program_manager

        # only testing "Status", "Completed", "Completed Options"
        manager.update_program_data("STATUS", "Sell")
        assert manager.get_program_data("STATUS") == "Sell"

        manager.update_program_data("COMPLETED", 1)
        assert manager.get_program_data("COMPLETED") == 1

        manager.update_program_data("COMPLETED_OPTIONS", 1)
        assert manager.get_program_data("COMPLETED_OPTIONS") == 1

    def test_program_manager_update_data_for_invalid_key(self, program_manager):
        _, manager = program_manager

        with pytest.raises(KeyError) as error:
            manager.update_program_data("INVALID_KEY", "Sell")
