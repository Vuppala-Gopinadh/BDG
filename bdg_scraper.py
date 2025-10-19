import asyncio
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from database import collection  # your MongoDB connection
from model_updater import update_model

# -------------------- Selenium setup --------------------
options = Options()
options.headless = True  # run in background
driver = webdriver.Chrome(options=options)

URL = "https://bdgwink.me/#/saasLottery/WinGo?gameCode=WinGo_30S&lottery=WinGo"

# -------------------- Fetch results from page --------------------
def get_latest_result():
    driver.get(URL)
    
    # Wait a few seconds for JS to load
    driver.implicitly_wait(5)

    # Find the element(s) containing number, color, size
    # ⚠ You need to adjust the selectors based on actual DOM
    try:
        number = int(driver.find_element(By.CSS_SELECTOR, ".number-class").text)
        color = driver.find_element(By.CSS_SELECTOR, ".color-class").text
        size = driver.find_element(By.CSS_SELECTOR, ".size-class").text
    except Exception as e:
        print("Error fetching data:", e)
        return None

    return {
        "number": number,
        "color": color,
        "size": size,
        "timestamp": datetime.datetime.utcnow()
    }

# -------------------- Async loop to update model --------------------
async def fetch_loop():
    while True:
        result = get_latest_result()
        if result:
            next_red_prob = await update_model(result, collection)
            result["next_red_probability"] = next_red_prob
            await collection.insert_one(result)
            print(f"[{datetime.datetime.utcnow()}] Fetched: {result}")
        await asyncio.sleep(30)  # wait for next round

# -------------------- Start --------------------
if __name__ == "__main__":
    asyncio.run(fetch_loop())
