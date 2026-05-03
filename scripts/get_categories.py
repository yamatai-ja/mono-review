import requests
import os
import sys
from dotenv import load_dotenv

# 出力を UTF-8 に設定
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
domain = os.getenv('MICROCMS_SERVICE_DOMAIN')
key = os.getenv('MICROCMS_API_KEY')

if not domain or not key:
    print("Error: MICROCMS_SERVICE_DOMAIN or MICROCMS_API_KEY not found in .env")
    sys.exit(1)

url = f'https://{domain}.microcms.io/api/v1/categories'
headers = {'X-MICROCMS-API-KEY': key}

try:
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    contents = res.json().get('contents', [])
    for c in contents:
        print(f"{c['id']}: {c['name']}")
except Exception as e:
    print(f"Error: {e}")
