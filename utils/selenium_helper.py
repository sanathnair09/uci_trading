from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import undetected_chromedriver as uc  # type: ignore[import-untyped]

from brokers import BASE_PATH


class CustomChromeInstance:

    @staticmethod
    def createInstance() -> webdriver.Chrome:
        options = webdriver.ChromeOptions()

        options.add_argument("--start-maximized")
        # Adding argument to disable the AutomationControlled flag
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Exclude the collection of enable-automation switches
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }

        options.add_experimental_option("prefs", prefs)
        # Turn-off userAutomationExtension
        # options.add_experimental_option("useAutomationExtension", False)
        return webdriver.Chrome(options=options)

    def __init__(self, undetected: bool = False) -> None:
        # Create Chromeoptions instance
        options = webdriver.ChromeOptions()
        options.add_argument("--log-level=3")
        options.add_argument("--start-maximized")
        # Adding argument to disable the AutomationControlled flag
        options.add_argument("--disable-blink-features=AutomationControlled")
        if not undetected:
            # Exclude the collection of enable-automation switches
            options.add_experimental_option("excludeSwitches", ["enable-automation"])

            prefs = {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "download.default_directory": str(BASE_PATH / "data"),
            }

            options.add_experimental_option("prefs", prefs)
            self._driver = webdriver.Chrome(service=Service(), options=options)
        else:
            self._driver = uc.Chrome(options=options)

        self._actions = ActionChains(self._driver)

    def open(self, page: str) -> None:
        self._driver.get(page)

    def _findInElem(self, by: str, id: str) -> WebElement:
        return self._driver.find_element(by, id)

    def switchToFrame(self, id: str) -> None:
        elem = self._findInElem(By.ID, id)
        self._driver.switch_to.frame(elem)

    def resetFrame(self) -> None:
        self._driver.switch_to.default_content()

    def find(self, by: str, id: str) -> WebElement:
        return self._findInElem(by, id)

    def waitToClick(self, id: str) -> None:
        wait = WebDriverWait(self._driver, 10)
        element = wait.until(EC.element_to_be_clickable((By.ID, id)))
        element.click()

    def waitForElementToLoad(self, by: str, elem: str, timeout: int = 10) -> WebElement:
        res = WebDriverWait(self._driver, timeout).until(
            EC.presence_of_element_located((by, elem))
        )
        return res

    def sendKeyboardInput(self, elem: WebElement, input: str) -> None:
        elem.clear()
        elem.send_keys(input)

    def scroll(self, amount: int) -> None:
        self._actions.scroll_by_amount(0, amount).perform()

    def scroll_to_element(self, elem: WebElement) -> None:
        self._actions.move_to_element(elem).perform()

    def sendKeys(self, keys: str) -> None:
        self._actions.send_keys(keys).perform()

    def get_page_source(self) -> str:
        return self._driver.page_source

    def refresh(self) -> None:
        self._driver.refresh()


if __name__ == "__main__":
    c = CustomChromeInstance()
    c.open("https://www.google.com")
