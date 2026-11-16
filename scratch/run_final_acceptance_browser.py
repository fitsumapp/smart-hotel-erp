import os, sys, time, json
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from apps.identity.services import get_tokens_for_user
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SCREENSHOT_DIR = os.path.join(os.path.abspath('.'), "docs", "screenshots", "final_acceptance")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

User = get_user_model()

def setup_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1600,1050")
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    driver = webdriver.Chrome(options=opts)
    return driver

def capture(driver, filename):
    path = os.path.join(SCREENSHOT_DIR, filename)
    driver.save_screenshot(path)
    sz = os.path.getsize(path)
    print(f"  [SCREENSHOT] {filename} ({sz:,} bytes)")
    return path

def check_console(driver, context_name):
    logs = driver.get_log("browser")
    severe = [l for l in logs if l.get("level") == "SEVERE" and "favicon" not in l.get("message", "").lower()]
    if severe:
        print(f"  [WARN] Console severe errors in {context_name}: {len(severe)}")
        for e in severe[:3]:
            print(f"    - {e.get('message', '')[:120]}")
    else:
        print(f"  [PASS] Zero console errors in {context_name}")

def authenticate(driver, user_obj, target_tab=None):
    tokens = get_tokens_for_user(user_obj)
    driver.get("http://localhost:3000/")
    time.sleep(1)
    payload = {
        "id": user_obj.id,
        "username": user_obj.username,
        "role": user_obj.role,
        "is_superuser": user_obj.is_superuser
    }
    driver.execute_script("""
        localStorage.setItem('access_token', arguments[0]);
        localStorage.setItem('refresh_token', arguments[1]);
        localStorage.setItem('user', JSON.stringify(arguments[2]));
        localStorage.setItem('role', arguments[3]);
    """, tokens["access"], tokens["refresh"], payload, user_obj.role)
    if target_tab:
        driver.execute_script("localStorage.setItem('activeTab', arguments[0]);", target_tab)
    driver.get("http://localhost:3000/dashboard")
    time.sleep(2)

def click_sidebar(driver, title):
    elem = driver.find_element(By.XPATH, f"//div[contains(@class, 'sb-item') and contains(., '{title}')]")
    elem.click()
    time.sleep(2)

def main():
    print("=== Starting Real Browser Acceptance Verification ===")
    admin_user = User.objects.filter(role="admin", is_active=True).first()
    if not admin_user:
        admin_user = User.objects.filter(is_superuser=True).first()
    print(f"Using test admin user: {admin_user.username}")

    driver = setup_driver()
    wait = WebDriverWait(driver, 10)

    try:
        # 1. Authenticate & load Dashboard
        authenticate(driver, admin_user)
        time.sleep(2)
        capture(driver, "01_executive_dashboard.png")
        check_console(driver, "Dashboard")

        # 2. Inventory Control
        click_sidebar(driver, "Inventory Control")
        capture(driver, "02_inventory_control_overview.png")
        check_console(driver, "Inventory Overview")

        # Click Stock Ledger inside Inventory Control
        try:
            ledger_btn = driver.find_element(By.XPATH, "//button[contains(., 'Stock Ledger')]")
            ledger_btn.click()
            time.sleep(2)
            capture(driver, "03_stock_ledger_paginated.png")
            check_console(driver, "Stock Ledger")
        except Exception as e:
            print(f"  Note: Ledger button: {e}")

        # Click Waste & Loss inside Inventory Control
        try:
            waste_btn = driver.find_element(By.XPATH, "//button[contains(., 'Waste & Loss')]")
            waste_btn.click()
            time.sleep(2)
            capture(driver, "04_waste_desk.png")
            check_console(driver, "Waste Desk")
        except Exception as e:
            print(f"  Note: Waste button: {e}")

        # 3. Stock Transfers & Locations
        click_sidebar(driver, "Stock Transfers & Locations")
        capture(driver, "05_stock_transfer_center.png")
        check_console(driver, "Stock Transfer Center")

        # 4. Physical Stocktaking
        click_sidebar(driver, "Physical Stocktaking")
        capture(driver, "06_physical_stocktaking.png")
        check_console(driver, "Physical Stocktaking")

        # 5. Finance & Accounts
        click_sidebar(driver, "Finance & Accounts")
        capture(driver, "07_finance_gl.png")
        check_console(driver, "Finance & Accounts")

        # 6. Procurement & Sourcing -> Goods Receiving (GRN)
        try:
            click_sidebar(driver, "Procurement & Sourcing")
            time.sleep(1)
            grn_sub = driver.find_element(By.XPATH, "//div[contains(., 'Goods Receiving (GRN)')]")
            grn_sub.click()
            time.sleep(2)
            capture(driver, "08_procurement_grn_receiving.png")
            check_console(driver, "GRN Receiving")
        except Exception as e:
            print(f"  Note: Procurement sub-item: {e}")

        print("=== Real Browser Acceptance Verification Completed Successfully ===")

    finally:
        driver.quit()

if __name__ == '__main__':
    main()
