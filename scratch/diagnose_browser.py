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

User = get_user_model()
admin = User.objects.filter(role='admin', is_active=True).first()
admin_jwt = get_tokens_for_user(admin)['access']
user_payload = {'id': admin.id, 'username': admin.username, 'role': 'admin', 'is_superuser': True}

chrome_opts = Options()
chrome_opts.add_argument('--headless=new')
chrome_opts.add_argument('--no-sandbox')
chrome_opts.add_argument('--disable-dev-shm-usage')
chrome_opts.add_argument('--window-size=1600,1050')

driver = webdriver.Chrome(options=chrome_opts)
try:
    driver.get('http://localhost:3000/')
    time.sleep(2)
    driver.execute_script(f"""
        localStorage.setItem('access_token', '{admin_jwt}');
        localStorage.setItem('refresh_token', '{admin_jwt}');
        localStorage.setItem('user', JSON.stringify({json.dumps(user_payload)}));
        localStorage.setItem('role', 'admin');
    """)
    driver.get('http://localhost:3000/dashboard')
    time.sleep(3)

    # Click Physical Stocktaking
    stk_nav = driver.find_element(By.XPATH, "//*[contains(text(), 'Physical Stocktaking')]")
    driver.execute_script('arguments[0].click();', stk_nav)
    time.sleep(3)

    # Find all buttons with exact text 'Count'
    count_buttons = [b for b in driver.find_elements(By.TAG_NAME, 'button') if b.text.strip() == 'Count']
    print(f'Buttons with exact text Count: {len(count_buttons)}')
    if count_buttons:
        driver.execute_script('arguments[0].click();', count_buttons[0])
        time.sleep(3)
        inputs = driver.find_elements(By.XPATH, "//input[@type='number']")
        print(f'Number inputs after clicking exact Count button: {len(inputs)}')
        print('Page snippet:\n', driver.find_element(By.TAG_NAME, 'body').text[:600])
finally:
    driver.quit()

