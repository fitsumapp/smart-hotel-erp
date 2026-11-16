import os, sys, django
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time, json
from apps.identity.services import get_tokens_for_user
from django.contrib.auth import get_user_model

User = get_user_model()
staff_b = User.objects.get(id=38)
tokens = get_tokens_for_user(staff_b)

chrome_opts = Options()
chrome_opts.add_argument('--headless=new')
chrome_opts.add_argument('--no-sandbox')
chrome_opts.add_argument('--window-size=1600,1050')
driver = webdriver.Chrome(options=chrome_opts)

try:
    driver.get('http://localhost:3000/')
    time.sleep(1)
    payload = {'id': staff_b.id, 'username': staff_b.username, 'role': 'admin', 'is_superuser': False}
    driver.execute_script('''
        localStorage.setItem('access_token', arguments[0]);
        localStorage.setItem('refresh_token', arguments[1]);
        localStorage.setItem('user', JSON.stringify(arguments[2]));
        localStorage.setItem('role', 'admin');
    ''', tokens['access'], tokens['refresh'], payload)

    driver.get('http://localhost:3000/dashboard')
    time.sleep(3)
    stk_btn = driver.find_element(By.XPATH, "//*[contains(text(), 'Physical Stocktaking')]")
    stk_btn.click()
    time.sleep(4)

    tbody = driver.find_element(By.TAG_NAME, 'tbody')
    print('=== TBODY TEXT FOR STAFF B ===')
    print(tbody.text)
finally:
    driver.quit()

