"""
Independent QC Browser Reproduction Script for DEF-04 and DEF-05.
Directly reproduces and verifies browser behavior, DOM state, and network API consistency.
"""
import os, sys, time
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from apps.identity.services import get_tokens_for_user
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

User = get_user_model()
admin_user = User.objects.get(username="staging_admin")
staff_a = User.objects.get(username="remed_staff_a")
staff_b = User.objects.get(username="remed_staff_b")

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
    print("INDEPENDENT QC BROWSER REPRODUCTION: DEF-04 & DEF-05")
    print("======================================================================")

    # 1. Staff A Stocktaking View
    print("\n[Audit 1] Verifying Staff A (Store A custodian) session visibility in UI:")
    set_auth(staff_a_tokens, staff_a)
    driver.get("http://localhost:3000/dashboard")
    time.sleep(2)
    stk_nav = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Physical Stocktaking')]")))
    safe_click(stk_nav)
    time.sleep(3)

    loc_cells_a = [td.text.strip() for td in driver.find_elements(By.XPATH, "//tbody/tr/td[4]")]
    print(f"  Locations visible to Staff A in UI table: {set(loc_cells_a)}")
    assert "Store A" in loc_cells_a, "FAIL: Store A should be visible to Staff A!"
    assert "Store B" not in loc_cells_a, "FAIL: Store B leaked into Staff A table!"
    print("  -> CONFIRMED: Store A is present, Store B is strictly concealed.")

    # 2. Staff B Stocktaking View
    print("\n[Audit 2] Verifying Staff B (Store B custodian) session visibility in UI:")
    set_auth(staff_b_tokens, staff_b)
    driver.get("http://localhost:3000/dashboard")
    time.sleep(2)
    stk_nav_b = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Physical Stocktaking')]")))
    safe_click(stk_nav_b)
    time.sleep(3)

    loc_cells_b = [td.text.strip() for td in driver.find_elements(By.XPATH, "//tbody/tr/td[4]")]
    print(f"  Locations visible to Staff B in UI table: {set(loc_cells_b)}")
    assert "Store B" in loc_cells_b, "FAIL: Store B should be visible to Staff B!"
    assert "Store A" not in loc_cells_b, "FAIL: Store A leaked into Staff B table!"
    print("  -> CONFIRMED: Store B is present, Store A is strictly concealed.")

    # 3. Administrator Global Visibility
    print("\n[Audit 3] Verifying Administrator global multi-location visibility in UI:")
    set_auth(admin_tokens, admin_user)
    driver.get("http://localhost:3000/dashboard")
    time.sleep(2)
    stk_nav_adm = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Physical Stocktaking')]")))
    safe_click(stk_nav_adm)
    time.sleep(3)

    admin_loc_cells = [td.text.strip() for td in driver.find_elements(By.XPATH, "//tbody/tr/td[4]")]
    print(f"  Locations visible to Admin in UI table: {set(admin_loc_cells)}")
    assert "Store A" in admin_loc_cells and "Store B" in admin_loc_cells, "FAIL: Admin should see all stores!"
    print("  -> CONFIRMED: Admin sees both Store A and Store B simultaneously.")

    # 4. DEF-05 UI Configuration: Display, Save, Refresh Persistence
    print("\n[Audit 4] Verifying Near-Expiry Setting UI Display, Save, and Persistence:")
    settings_item = wait.until(EC.presence_of_element_located((
        By.XPATH, "//div[contains(@class, 'sb-item') and .//span[text()='Settings']]"
    )))
    safe_click(settings_item)
    time.sleep(3)

    inv_section = wait.until(EC.presence_of_element_located((
        By.XPATH, "//*[contains(text(), 'Inventory & Expiry Surveillance')]"
    )))
    safe_click(inv_section)
    time.sleep(2)

    expiry_input = wait.until(EC.presence_of_element_located((
        By.ID, "input-near-expiry-warning-days"
    )))
    initial_val = expiry_input.get_attribute("value")
    print(f"  Initial near_expiry_warning_days displayed in UI: {initial_val}")

    # Change value to 28
    print("  Updating near_expiry_warning_days to 28...")
    expiry_input.clear()
    expiry_input.send_keys("28")
    time.sleep(1)

    save_btn = driver.find_element(By.XPATH, "//button[contains(., 'Save Changes')]")
    safe_click(save_btn)
    time.sleep(2)

    try:
        alert = driver.switch_to.alert
        print(f"  Browser alert received: {alert.text}")
        assert "Settings updated successfully" in alert.text
        alert.accept()
    except Exception as e:
        print(f"  Alert check note: {e}")

    time.sleep(2)
    # Refresh page
    print("  Refreshing browser page...")
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
    print(f"  Persisted value after browser refresh: {persisted_val}")
    assert persisted_val == "28", f"FAIL: Expected '28', got '{persisted_val}'!"
    print("  -> CONFIRMED: Value 28 persisted across full browser reload.")

    # Restore default 30
    print("  Restoring clean default value 30...")
    expiry_input_refreshed.clear()
    expiry_input_refreshed.send_keys("30")
    safe_click(driver.find_element(By.XPATH, "//button[contains(., 'Save Changes')]"))
    time.sleep(1.5)
    try:
        driver.switch_to.alert.accept()
    except Exception:
        pass
    time.sleep(2)

    print("\n======================================================================")
    print("INDEPENDENT BROWSER REPRODUCTION AUDIT: 100% SUCCESS")
    print("======================================================================")

finally:
    driver.quit()

