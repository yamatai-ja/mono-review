import os
import re
import sys
import requests
import markdown
from dotenv import load_dotenv

# 出力を UTF-8 に設定
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

def upload_article(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. タイトルの抽出
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "Untitled"

    # 2. メタディスクリプションの抽出（より柔軟に）
    # 「メタディスクリプション」という見出しの後のテキストを、次の「---」や「この記事は」まで取得
    desc_block = re.search(r'(?:メタディスクリプション|\*\*メタディスクリプション\*\*)\n+(.+?)(?:\n---|\nこの記事は|\n#|$)', content, re.DOTALL)
    description = desc_block.group(1).strip() if desc_block else ""

    # 3. 各種データの抽出（ファイル全体から柔軟に検索）
    def get_meta(pattern, text, default=None):
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else default

    slug = get_meta(r'【URLスラッグ】:\s*[\n\r]*\s*([a-z0-9-]+)', content)
    
    rating_val = get_meta(r'【評価スコア】:\s*[\n\r]*\s*([\d.]+)', content, "0.0")
    rating = float(rating_val)
    
    # メリット・デメリットはブロックで探す
    pros = get_meta(r'【メリット（Pros）】:\s*[\n\r]*\s*(.+?)\n\n【', content)
    if not pros:
        pros = get_meta(r'【メリット（Pros）】:\s*[\n\r]*\s*(.+?)(?:\n|$)', content)
        
    cons = get_meta(r'【デメリット（Cons）】:\s*[\n\r]*\s*(.+?)(?:\n\n【|\n\n---|\s*$)', content)

    category_name = get_meta(r'【カテゴリー】:\s*[\n\r]*\s*(.+?)(?:\s*→|\n|$)', content, "")

    # カテゴリーIDへのマッピング（最新のIDに合わせて更新）
    category_map = {
        "デジタル・ガジェット": "digital-gadget",
        "ガジェット": "digital-gadget",
        "スポーツ": "sports-hobby",
        "趣味": "sports-hobby",
        "キッチン": "home-kitchen",
        "ホーム": "home-kitchen"
    }
    category_id = None
    for name, cid in category_map.items():
        if name in category_name:
            category_id = cid
            break

    # 4. 本文の抽出と加工
    def clean_text(text):
        # 引用タグの削除
        text = re.sub(r'\[cite_start\]', '', text)
        text = re.sub(r'\[cite: [^\]]+\]', '', text)
        return text

    body_md = content
    # タイトル、メタディスクリプション、入稿用データセクションを除去
    body_md = re.sub(r'#\s+.+\n', '', body_md, 1)
    body_md = re.sub(r'--- microCMS 入稿用データ ---.*', '', body_md, flags=re.DOTALL)
    body_md = re.sub(r'\*\*メタディスクリプション\*\*\n?.*?\n', '', body_md)
    body_md = re.sub(r'メタディスクリプション：?.*?\n', '', body_md)
    
    body_md = clean_text(body_md)
    title = clean_text(title)
    description = clean_text(description)

    body_html = markdown.markdown(body_md.strip(), extensions=['tables', 'fenced_code', 'nl2br'])

    # 5. microCMS API 実行
    domain = os.getenv('MICROCMS_SERVICE_DOMAIN')
    key = os.getenv('MICROCMS_API_KEY')
    
    headers = {
        "Content-Type": "application/json",
        "X-MICROCMS-API-KEY": key
    }
    
    payload = {
        "id": slug,
        "title": title,
        "description": description,
        "content": body_html,
        "rating": rating,
        "review_pros": pros,
        "review_cons": cons
    }
    
    if category_id:
        payload["category"] = category_id

    print(f"Uploading: {title} (ID: {slug})...")
    
    # すでに記事がある場合は PATCH、ない場合は POST
    post_url = f"https://{domain}.microcms.io/api/v1/blogs"
    check_url = f"{post_url}/{slug}"
    
    check_res = requests.get(check_url, headers=headers)
    
    if check_res.status_code == 200:
        print("Existing article found. Updating (PATCH)...")
        res = requests.patch(check_url, headers=headers, json=payload)
    else:
        print("New article. Creating (POST)...")
        res = requests.post(post_url, headers=headers, json=payload)
    
    if res.status_code == 201:
        print("Successfully uploaded to microCMS!")
        print(f"URL: https://{domain}.microcms.io/apis/blogs/contents/{slug}")
    else:
        print(f"Failed to upload: {res.status_code}")
        print(res.text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python upload_to_microcms.py <path_to_markdown_file>")
    else:
        upload_article(sys.argv[1])
