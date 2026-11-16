"""
Selenium Real-Browser Acceptance Script for Limitations Remediation (DEF-04 and DEF-05).
Captures screenshots proving:
1. System Settings displays Near-Expiry Warning Window (DEF-05)
2. Admin modifies and saves near_expiry_warning_days (DEF-05)
3. Persisted value survives page refresh (DEF-05)
4. Staff A (Location A custodian) sees Location A and is blocked from Location B (DEF-04)
5. Staff B (Location B custodian) sees Location B and is blocked from Location A (DEF-04)
6. Admin retains global visibility across all locations (DEF-04)
"""
import os
import sys
import time
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from apps.identity.services import get_tokens_for_user
from hotel.models import StockLocation, StocktakeSession, StocktakeSchedule, SystemSettings
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SCREENSHOT_DIR = os.path.join(os.getcwd(), "docs", "screenshots", "limitations_remediation")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

User = get_user_model()
admin_user = User.objects.get(id=1) # staging_admin
staff_a = User.objects.get(id=37)   # remed_staff_a
staff_b = User.objects.get(id=38)   # remed_staff_b

admin_tokens = get_tokens_for_user(admin_user)
staff_a_tokens = get_tokens_for_user(staff_a)
staff_b_tokens = get_tokens_for_user(staff_b)

chrome_opts = Options()
chrome_opts.add_argument("--headless=new")
chrome_opts.add_argument("--no-sandbox")
chrome_opts.add_argument("--disable-dev-shm-usage")
chrome_opts.add_argument("--disable-gpu")
chrome_opts.add_argument("--window-size=1600,1050")

driver = webdriver.Chrome(options=chrome_opts)
wait = WebDriverWait(driver, 15)

def safe_click(elem):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
    time.sleep(0.5)
    try:
        elem.click()
    except Exception:
        driver.execute_script("arguments[0].click();", elem)

def capture(name):
    path = os.path.join(SCREENSHOT_DIR, name)
    driver.save_screenshot(path)
    print(f"  -> Captured: {name} ({os.path.getsize(path)} bytes)")

def set_auth(tokens, user_obj, layout_role="admin"):
    try:
        driver.switch_to.alert.accept()
        time.sleep(0.5)
    except Exception:
        pass
    driver.get("http://localhost:3000/")
    time.sleep(1)
    payload = {
        "id": user_obj.id,
        "username": user_obj.username,
        "role": layout_role,
        "is_superuser": user_obj.is_superuser
    }
    driver.execute_script("""
        localStorage.setItem('access_token', arguments[0]);
        localStorage.setItem('refresh_token', arguments[1]);
        localStorage.setItem('user', JSON.stringify(arguments[2]));
        localStorage.setItem('role', arguments[3]);
    """, tokens["access"], tokens["refresh"], payload, layout_role)

try:
    print("======================================================================")
    print("REAL-BROWSER ACCEPTANCE: DEF-04 LOCATION SCOPING & DEF-05 SETTINGS UI")
    print("======================================================================")

    # -------------------------------------------------------------------------
    # PART 1: DEF-05 — System Settings Manager in React SPA
    # -------------------------------------------------------------------------
    print("\n[Step 1] Logging in as Administrator and loading System Configuration...")
    set_auth(admin_tokens, admin_user)
    driver.get("http://localhost:3000/dashboard")
    time.sleep(3)

    # Navigate to Settings via sidebar
    print("  Locating 'Settings' in the sidebar...")
    settings_item = wait.until(EC.presence_of_element_located((
        By.XPATH, "//div[contains(@class, 'sb-item') and .//span[text()='Settings']]"
    )))
    safe_click(settings_item)
    time.sleep(3)

    # Locate and open "Inventory & Expiry Surveillance" accordion
    print("  Locating 'Inventory & Expiry Surveillance' section...")
    inv_section = wait.until(EC.presence_of_element_located((
        By.XPATH, "//*[contains(text(), 'Inventory & Expiry Surveillance')]"
    )))
    safe_click(inv_section)
    time.sleep(2)

    # Capture initial view of settings
    capture("01_settings_navigated_and_near_expiry_visible.png")

    # Locate input field
    expiry_input = wait.until(EC.presence_of_element_located((
        By.ID, "input-near-expiry-warning-days"
    )))
    current_val = expiry_input.get_attribute("value")
    print(f"  Current near_expiry_warning_days value in UI: {current_val}")

    # Step 2: Modify setting to 21 days and click Save Changes
    print("\n[Step 2] Modifying near-expiry warning days to 21 and saving...")
    expiry_input.clear()
    expiry_input.send_keys("21")
    time.sleep(1)

    # Click Save Changes button
    save_btn = driver.find_element(By.XPATH, "//button[contains(., 'Save Changes')]")
    safe_click(save_btn)
    time.sleep(2)

    # Handle alert if present
    try:
        alert = driver.switch_to.alert
        print(f"  Alert text received: {alert.text}")
        alert.accept()
    except Exception:
        pass
    time.sleep(2)
    capture("02_settings_changed_and_saved.png")

    # Step 3: Refresh page and verify persistence
    print("\n[Step 3] Refreshing page to verify persistence...")
    driver.refresh()
    time.sleep(3)

    settings_item_refreshed = wait.until(EC.presence_of_element_located((
        By.XPATH, "//div[contains(@class, 'sb-item') and .//span[text()='Settings']]"
    )))
    safe_click(settings_item_refreshed)
    time.sleep(3)

    inv_section_refreshed = wait.until(EC.presence_of_element_located((
        By.XPATH, "//*[contains(text(), 'Inventory & Expiry Surveillance')]"
    )))
    safe_click(inv_section_refreshed)
    time.sleep(2)

    expiry_input_refreshed = wait.until(EC.presence_of_element_located((
        By.ID, "input-near-expiry-warning-days"
    )))
    persisted_val = expiry_input_refreshed.get_attribute("value")
    print(f"  Persisted near_expiry_warning_days value after refresh: {persisted_val}")
    assert persisted_val == "21", f"Expected '21', got '{persisted_val}'!"
    capture("03_settings_persisted_after_refresh.png")

    # Revert back to 30 days for clean state
    print("  Restoring default 30 days...")
    expiry_input_refreshed.clear()
    expiry_input_refreshed.send_keys("30")
    safe_click(driver.find_element(By.XPATH, "//button[contains(., 'Save Changes')]"))
    time.sleep(1.5)
    try:
        driver.switch_to.alert.accept()
    except Exception:
        pass
    time.sleep(2)

    # -------------------------------------------------------------------------
    # PART 2: DEF-04 — Location Scoping in Stocktaking Center
    # -------------------------------------------------------------------------
    # Step 4: Login as remed_staff_a (Store A custodian)
    print("\n[Step 4] Logging in as remed_staff_a (Location A custodian)...")
    set_auth(staff_a_tokens, staff_a)
    driver.get("http://localhost:3000/dashboard")
    time.sleep(2)

    stk_nav = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Physical Stocktaking')]")))
    safe_click(stk_nav)
    time.sleep(3)

    capture("04_location_a_staff_sessions_filtered.png")
    loc_cells_a = [td.text.strip() for td in driver.find_elements(By.XPATH, "//tbody/tr/td[4]")]
    print(f"  Location column values for Staff A: {set(loc_cells_a)}")
    assert "Store A" in loc_cells_a, "Store A missing from Location A staff session view!"
    assert "Store B" not in loc_cells_a, "Store B leaked into Location A staff session view!"

    # Step 5: Check Schedules tab as remed_staff_a
    print("\n[Step 5] Checking Schedules tab for remed_staff_a...")
    sched_tab_btns = [b for b in driver.find_elements(By.TAG_NAME, "button") if "Schedule" in b.text]
    if sched_tab_btns:
        safe_click(sched_tab_btns[0])
        time.sleep(2)
        capture("05_location_a_staff_schedules_filtered.png")
        sched_tbody_a = driver.find_element(By.TAG_NAME, "tbody").text
        print(f"  Checking Store B schedule concealment: {'Store B Weekly Schedule' not in sched_tbody_a}")
        assert "Store B Weekly Schedule" not in sched_tbody_a, "Store B schedule leaked to Staff A!"

    # Step 6: Login as remed_staff_b (Store B custodian)
    print("\n[Step 6] Logging in as remed_staff_b (Location B custodian)...")
    set_auth(staff_b_tokens, staff_b)
    driver.get("http://localhost:3000/dashboard")
    time.sleep(2)

    stk_nav_b = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Physical Stocktaking')]")))
    safe_click(stk_nav_b)
    time.sleep(3)

    capture("06_location_b_staff_sessions_filtered.png")
    loc_cells_b = [td.text.strip() for td in driver.find_elements(By.XPATH, "//tbody/tr/td[4]")]
    print(f"  Location column values for Staff B: {set(loc_cells_b)}")
    assert "Store B" in loc_cells_b, "Store B missing from Location B staff session view!"
    assert "Store A" not in loc_cells_b, "Store A leaked into Location B staff session view!"

    # Step 7: Login as Administrator and verify global visibility
    print("\n[Step 7] Logging in as Administrator and verifying global multi-location visibility...")
    set_auth(admin_tokens, admin_user)
    driver.get("http://localhost:3000/dashboard")
    time.sleep(2)

    stk_nav_adm = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Physical Stocktaking')]")))
    safe_click(stk_nav_adm)
    time.sleep(3)

    capture("07_admin_full_visibility.png")
    admin_loc_cells = [td.text.strip() for td in driver.find_elements(By.XPATH, "//tbody/tr/td[4]")]
    print(f"  Location column values for Admin: {set(admin_loc_cells)}")
    assert "Store A" in admin_loc_cells, "Store A missing from Admin table!"
    assert "Store B" in admin_loc_cells, "Store B missing from Admin table!"

    print("\n======================================================================")
    print("ALL REAL-BROWSER ACCEPTANCE TESTS PASSED 100%!")
    print("======================================================================")

finally:
    driver.quit()

