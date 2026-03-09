from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

def enviar_whatsapp_selenium(telefono: str, mensaje: str):
    url = f"https://web.whatsapp.com/send?phone={telefono}&text={mensaje}"
    chrome_options = Options()
    chrome_options.add_argument("--user-data-dir=selenium")  # para mantener sesión iniciada

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)
