from pathlib import Path

from loguru import logger
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

from brokers import BASE_PATH


class CustomChromeInstance:

    @staticmethod
    def createInstance():
        options = webdriver.ChromeOptions()
        
        options.add_argument("--start-maximized")
        # Adding argument to disable the AutomationControlled flag
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Exclude the collection of enable-automation switches
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        prefs = {"credentials_enable_service": False,
                 "profile.password_manager_enabled": False}
        
        options.add_experimental_option("prefs", prefs)
        # Turn-off userAutomationExtension
        # options.add_experimental_option("useAutomationExtension", False)
        return webdriver.Chrome(options = options)

    def __init__(self) -> None:
        # Create Chromeoptions instance 
        options = webdriver.ChromeOptions()
        options.add_argument('--log-level=3')
        options.add_argument("--start-maximized")
        # Adding argument to disable the AutomationControlled flag 
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Exclude the collection of enable-automation switches 
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "download.default_directory": str(BASE_PATH / "data")
        }

        options.add_experimental_option("prefs", prefs)

        # Turn-off userAutomationExtension 
        # options.add_experimental_option("useAutomationExtension", False)
        self._driver = webdriver.Chrome(service = Service(), options = options)
        self._actions = ActionChains(self._driver)
        # print(self._driver.service.path)
        # self._driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})") 

    def open(self, page: str):
        self._driver.get(page)

    def _findInElem(self, elem, by, id: str):
        return elem.find_element(by, id)

    def switchToFrame(self, id: str):
        elem = self._findInElem(self._driver, By.ID, id)
        self._driver.switch_to.frame(elem)

    def resetFrame(self):
        self._driver.switch_to.default_content()

    def find(self, by, id: str, elem = None):
        return self._findInElem(elem, by, id) if elem else self._findInElem(self._driver, by, id)

    def waitToClick(self, id: str):
        wait = WebDriverWait(self._driver, 10)
        element = wait.until(EC.element_to_be_clickable((By.ID, id)))
        element.click()

    def waitForElementToLoad(self, by, elem: str, timeout: int = 10):
        res = WebDriverWait(self._driver, timeout).until(EC.presence_of_element_located((by, elem)))
        return res

    def waitForTextInValue(self, by, elem, text: str):
        return WebDriverWait(self._driver, 10).until(
            EC.text_to_be_present_in_element_value(
                (by, elem), text_ = text)
        )

    def sendKeyboardInput(self, elem, input: str):
        elem.clear()
        elem.send_keys(input)

    def scroll(self, amount):
        self._actions.scroll_by_amount(0, amount).perform()

    def sendKeys(self, keys):
        self._actions.send_keys(keys).perform()

    def get_page_source(self):
        return self._driver.page_source

    def current_url(self):
        return self._driver.current_url
    def get_elem_source(self, element: WebElement):
        return element.get_attribute("outerHTML")

    def refresh(self):
        self._driver.refresh()


if __name__ == '__main__':
    c = CustomChromeInstance()
    c.open("https://www.google.com")