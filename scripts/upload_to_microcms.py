import os
import re
import sys
import requests
import markdown
import yaml
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

    # 1. YAML フロントマターの解析
    frontmatter = {}
    body_md = content
    
    if content.startswith('---'):
        parts = re.split(r'^---\s*$', content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1])
                body_md = parts[2]
            except Exception as e:
                print(f"Warning: Failed to parse YAML frontmatter: {e}")

    # 2. データの抽出（フロントマター優先、なければ正規表現でフォールバック）
    def get_val(key, pattern, text, default=None):
        if key in frontmatter:
            return frontmatter[key]
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else default

    title = frontmatter.get('title')
    if not title:
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else "Untitled"

    description = frontmatter.get('description')
    if not description:
        desc_block = re.search(r'(?:メタディスクリプション|\*\*メタディスクリプション\*\*)\n+(.+?)(?:\n---|\nこの記事は|\n#|$)', content, re.DOTALL)
        description = desc_block.group(1).strip() if desc_block else ""

    slug = frontmatter.get('slug')
    if not slug:
        slug = get_val('slug', r'【URLスラッグ】:\s*([a-z0-9-]+)', content)
    if not slug:
        # ファイル名をスラッグのデフォルトにする
        slug = os.path.splitext(os.path.basename(file_path))[0]

    rating = float(frontmatter.get('rating', get_val('rating', r'【評価スコア】:\s*([\d.]+)', content, "0.0")))
    pros = frontmatter.get('review_pros', get_val('pros', r'【メリット（Pros）】:\s*(.+?)(?:\n\n【|\n---|$)', content))
    cons = frontmatter.get('review_cons', get_val('cons', r'【デメリット（Cons）】:\s*(.+?)(?:\n\n【|\n---|$)', content))

    # カテゴリー処理
    category_id = None
    raw_categories = frontmatter.get('categories', [])
    if isinstance(raw_categories, list) and len(raw_categories) > 0:
        cat = raw_categories[0]
        if isinstance(cat, dict):
            category_id = cat.get('id')
        else:
            category_id = str(cat)
    
    if not category_id:
        category_name = get_val('category', r'【カテゴリー】:\s*(.+?)(?:\s*→|\n|$)', content, "")
        category_map = {
            "デジタル・ガジェット": "digital-gadget",
            "ガジェット": "digital-gadget",
            "スポーツ": "sports-hobby",
            "趣味": "sports-hobby",
            "キッチン": "home-kitchen",
            "ホーム": "home-kitchen"
        }
        for name, cid in category_map.items():
            if name in category_name:
                category_id = cid
                break

    # 商品情報（アフィリエイトリンク）の処理
    products_payload = []
    raw_products = frontmatter.get('products', [])
    if isinstance(raw_products, list):
        for p in raw_products:
            product_entry = {
                "fieldId": "product_card",
                "title": p.get('title', ''),
                "amazon_url": p.get('amazon_url', ''),
                "rakuten_url": p.get('rakuten_url', ''),
                "yahoo_url": p.get('yahoo_url', ''),
                # "price": p.get('price', '') # 400エラーの原因となるため一旦無効化
            }
            # if 'image' in p:
            #     img_data = p['image']
            #     if isinstance(img_data, dict) and 'url' in img_data:
            #         product_entry["image"] = {"url": img_data['url']}
            #     elif isinstance(img_data, str):
            #         product_entry["image"] = {"url": img_data}
            
            products_payload.append(product_entry)

    # 3. 本文の加工 (Markdown -> HTML)
    def clean_text(text):
        text = re.sub(r'\[cite_start\]', '', text)
        text = re.sub(r'\[cite: [^\]]+\]', '', text)
        return text

    body_md = clean_text(body_md)
    body_html = markdown.markdown(body_md.strip(), extensions=['tables', 'fenced_code', 'nl2br'])

    # 4. microCMS API 実行
    domain = os.getenv('MICROCMS_SERVICE_DOMAIN')
    key = os.getenv('MICROCMS_API_KEY')
    
    if not domain or not key:
        print("Error: MICROCMS_SERVICE_DOMAIN or MICROCMS_API_KEY not set in .env")
        return

    headers = {
        "Content-Type": "application/json",
        "X-MICROCMS-API-KEY": key
    }
    
    payload = {
        "title": title,
        "description": description,
        "content": body_html,
        "rating": rating,
        "review_pros": pros,
        "review_cons": cons,
        "products": products_payload
    }
    
    if category_id:
        payload["category"] = category_id

    print(f"Uploading: {title} (ID: {slug})...")
    
    post_url = f"https://{domain}.microcms.io/api/v1/blogs"
    check_url = f"{post_url}/{slug}"
    
    check_res = requests.get(check_url, headers=headers)
    
    if check_res.status_code == 200:
        print("Existing article found. Updating (PATCH)...")
        res = requests.patch(check_url, headers=headers, json=payload)
    else:
        print("New article. Creating (PUT)...")
        # IDを指定して作成する場合は PUT
        res = requests.put(check_url, headers=headers, json=payload)
    
    if res.status_code in [200, 201]:
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

