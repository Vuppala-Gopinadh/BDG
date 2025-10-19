import asyncio
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from database import collection 
from model_updater import update_model
from PIL import Image
import pytesseract
import re
import sys 


# --- ANSI COLOR CODES (Added to the top of the file) ---
ANSI_GREEN = '\033[92m'
ANSI_RED = '\033[91m'
ANSI_YELLOW = '\033[93m'
ANSI_END = '\033[0m'

# point pytesseract to exe if needed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- GLOBAL CONTROL FLAG ---
is_running = False
# ---------------------------

# Initial OCR test block (optional)
try:
    img = Image.open("result_box.png") 
    text = pytesseract.image_to_string(img, config="--psm 7")
    print("OCR Output:", text)
except FileNotFoundError:
    pass # Silent fail if file not found

# -------------------- Selenium setup --------------------
options = Options()
options.headless = False 
options.add_argument(r"user-data-dir=C:\Users\vgopi\ChromeAutomationProfile") 

driver = webdriver.Chrome(options=options)

GAME_URL = "https://bdgwink.me/#/saasLottery/WinGo?gameCode=WinGo_30S&lottery=WinGo"

# -------------------- Open game page --------------------
def open_game_page():
    driver.get(GAME_URL)
    driver.implicitly_wait(15)
    print("[INFO] Game page opened.")

try:
    game_history = driver.find_element(By.XPATH, "//*[contains(text(), 'Game history')]")
    container = game_history.find_element(By.XPATH, "following::div[1]")
    print("[DEBUG] Game history container text:")
    print(container.text[:1000])
except Exception as e:
    print("[DEBUG ERROR] Could not locate Game history container:", e)

def debug_page():
    print("[DEBUG] Dumping first 5000 chars of page source...")
    html = driver.page_source
    print(html[:5000])
    with open("page_dump.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[DEBUG] Saved full page to page_dump.html")

# -------------------- Extract latest result (FIXED) --------------------
def fetch_result():
    global is_running
    if not is_running:
        return None # Do nothing if paused

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Game history')]"))
        )
        page_text = driver.find_element(By.TAG_NAME, "body").text

        number_text = None
        period_id = "Unknown"
        size_from_number = None
        color_from_number = None
        raw_ocr_text = ""

        try:
            driver.save_screenshot("full_page.png")
            
            img = Image.open("full_page.png")
            x, y = 655, 175
            w, h = 460, 54
            cropped = img.crop((x, y, x + w, y + h))
            cropped.save("cropped_number.png")
            print("[DEBUG] Cropped number saved as cropped_number.png")

            ocr_attempts = [
                "--psm 7 -c tessedit_char_whitelist=0123456789 ",
                "--psm 6 -c tessedit_char_whitelist=0123456789 ",
                "--psm 8 -c tessedit_char_whitelist=0123456789 ",
            ]
            
            for cfg in ocr_attempts:
                raw_ocr_text = pytesseract.image_to_string(cropped, config=cfg).strip()
                print(f"[OCR TRY] config='{cfg}' → '{raw_ocr_text}'")
                if ' ' in raw_ocr_text and len(raw_ocr_text) > 5:
                    break
            
            if raw_ocr_text:
                parts = [p for p in raw_ocr_text.split() if p] 
                
                if len(parts) >= 2:
                    period_id = parts[0]
                    result_number_str = parts[-1] 

                    if result_number_str.isdigit() and len(result_number_str) == 1:
                        number_text = result_number_str
                        num = int(number_text)

                        if 0 <= num <= 9:
                            size_from_number = "Small" if num <= 4 else "Big"
                            color_from_number = "Red" if num % 2 == 0 else "Green"
                        else:
                            print(f"[DEBUG] Ignored invalid single-digit result: {num}")
                            number_text = None 
                    else:
                        print(f"[DEBUG] Failed to parse a single result digit from '{raw_ocr_text}'")
                elif len(parts) == 1 and len(parts[0]) > 10:
                    period_id = parts[0]
                    
            print(f"[OCR DEBUG] Raw Text: '{raw_ocr_text}', ID: {period_id}, Number: {number_text}, Size: {size_from_number}, Color: {color_from_number}")

        except Exception as ocr_e:
            print("[OCR ERROR] Could not OCR result box:", ocr_e)

        if period_id == "Unknown":
            match = re.search(r"\b20\d{11,}\b", page_text)
            period_id = match.group(0) if match else "Unknown"


        result = {
            "period": period_id, 
            "color": color_from_number,
            "size": size_from_number,
            "number": number_text, 
            "timestamp": datetime.datetime.utcnow()
        }

        print(f"[INFO] Parsed result: {result}")
        return result

    except Exception as e:
        print("[ERROR] Could not fetch result:", e)
        return None

# -------------------- Input Listener (NEW) --------------------
async def input_listener():
    global is_running
    print("\n--- Controls: Press 's' to START, 'x' to STOP, 'q' to QUIT ---\n")
    while True:
        try:
            # Note: This requires the script to be run in a terminal/console
            user_input = await asyncio.to_thread(input, f"Status: {'RUNNING' if is_running else 'STOPPED'}. Enter command: ")
            
            if user_input.lower() == 's':
                if not is_running:
                    is_running = True
                    print("\n[CONTROL] >>> ALGORITHM STARTED! Synchronization active. <<<\n")
            elif user_input.lower() == 'x':
                if is_running:
                    is_running = False
                    print("\n[CONTROL] >>> ALGORITHM STOPPED! Waiting for START command. <<<\n")
            elif user_input.lower() == 'q':
                print("[CONTROL] Quitting application.")
                # Force exit the entire application gracefully
                driver.quit()
                sys.exit(0)
            else:
                print("Invalid command. Use 's', 'x', or 'q'.")
        except EOFError:
            # Handle Ctrl+D or disconnection
            break
        except Exception as e:
            print(f"[INPUT ERROR] {e}")
            break

async def fetch_loop():
    while True:
        # PAUSE CHECK: Sleep while the algorithm is stopped
        if not is_running:
            await asyncio.sleep(0.1) 
            continue

        try:
            result = fetch_result()
            
            if result and result.get("number") is not None:
                
                # --- FIX: Convert the number string to an integer for model math ---
                model_result = result.copy()
                try:
                    # Convert the string number to integer before passing to model
                    model_result['number'] = int(model_result['number']) 
                except ValueError:
                    print(f"[ERROR] Failed to convert result number '{result['number']}' to integer. Skipping model update.")
                    await asyncio.sleep(10)
                    continue 
                
                # Train ALL models and get ALL predictions (returns a dict of probabilities)
                next_probs = await update_model(model_result, collection)

                # --- STORE ALL PREDICTIONS ---
                
                # Color Predictions
                result["prob_red"] = next_probs.get("prob_red")
                result["prob_green"] = next_probs.get("prob_green")
                result["prob_violet"] = next_probs.get("prob_violet")
                
                # Size Predictions
                result["prob_size_big"] = next_probs.get("prob_big")
                result["prob_size_small"] = next_probs.get("prob_small")
                
                # Number Predictions (Stored as a dictionary/JSON object)
                result["prob_numbers"] = next_probs.get("prob_numbers")

                # Store in MongoDB (using original result)
                await collection.insert_one(result)
                
                
                # --- START COLORIZED TERMINAL LOGIC ---
                
                p_r = result.get("prob_red", 0)
                p_g = result.get("prob_green", 0)
                p_v = result.get("prob_violet", 0)
                p_big = result.get("prob_size_big", 0)
                p_small = result.get("prob_size_small", 0)
                
                # 1. Color String (Highlight the highest probability above 35%)
                max_color_prob = max(p_r, p_g, p_v)
                
                color_str = f"R:{p_r}|G:{p_g}|V:{p_v}"
                
                if max_color_prob > 0.35: # Use 35% as a confidence threshold
                    if p_r == max_color_prob:
                        color_str = f"{ANSI_RED}R:{p_r}{ANSI_END}|G:{p_g}|V:{p_v}"
                    elif p_g == max_color_prob:
                        color_str = f"R:{p_r}|{ANSI_GREEN}G:{p_g}{ANSI_END}|V:{p_v}"
                    elif p_v == max_color_prob:
                        color_str = f"R:{p_r}|G:{p_g}|{ANSI_YELLOW}V:{p_v}{ANSI_END}"

                # 2. Size String (Highlight the highest probability)
                size_str = f"B:{p_big}|S:{p_small}"
                
                # --- CORRECTED LOGIC: Highlight the strictly highest prediction ---
                if p_big > p_small :
                    size_str = f"{ANSI_RED}BIG:{p_big}{ANSI_END}|S:{p_small}"
                elif p_small > p_big :
                    size_str = f"B:{p_big}|{ANSI_GREEN}SMALL:{p_small}{ANSI_END}"
                # If equal (0.5/0.5), no color is applied (default logic)
                
                # Print the enhanced log line
                print(
                    f"[{datetime.datetime.now(datetime.UTC)}] "
                    f"PERIOD: {result['period'][-4:]} | "
                    f"ACTUAL: {result['color']}-{result['size']} ({result['number']}) | "
                    f"PRED COLOR: [{color_str}] | PRED SIZE: [{size_str}]"
                )
                
                # --- END COLORIZED TERMINAL LOGIC ---

            else:
                # This handles OCR failure (transient) or insufficient data at start
                print("[INFO] No complete result fetched, retrying...")

        except Exception as e:
            print("[ERROR] Loop exception:", e)

        await asyncio.sleep(30) # wait for next result

# -------------------- Start --------------------
if __name__ == "__main__":
    print("[INFO] Make sure you are logged in and Chrome is closed before running.")
    open_game_page()
    
    # 1. DEFINE a main asynchronous function (main_async)
    async def main_async():
        # 2. RUN the two coroutines concurrently using asyncio.gather
        await asyncio.gather(fetch_loop(), input_listener())

    # 3. RUN the main asynchronous function
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[INFO] Application shut down by user.")
        driver.quit()

# HI 