import requests
import os
import re
import json
from dotenv import load_dotenv

# .env を読み込む
load_dotenv()

def sync():
    domain = os.getenv('MICROCMS_SERVICE_DOMAIN')
    api_key = os.getenv('MICROCMS_API_KEY')
    endpoint = "blogs" # 記事のAPIエンドポイント
    
    if not domain or not api_key:
        print("Error: MICROCMS_SERVICE_DOMAIN or MICROCMS_API_KEY is not set.")
        return

    url = f"https://{domain}.microcms.io/api/v1/{endpoint}?limit=100"
    headers = {"X-MICROCMS-API-KEY": api_key}
    
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print(f"Failed to fetch: {res.status_code}")
        print(res.text)
        return

    data = res.json()
    contents = data.get("contents", [])
    
    # 出力先ディレクトリ
    output_dir = "src/content/posts"
    os.makedirs(output_dir, exist_ok=True)

    for post in contents:
        slug = post.get("id")
        title = post.get("title", "")
        published_at = post.get("publishedAt", "")
        description = post.get("description", "")
        content = post.get("content", "")
        
        # カテゴリー情報
        category = post.get("category")
        category_json = ""
        if category:
            # オブジェクト形式で保存
            category_json = f"\n  - id: {category.get('id')}\n    name: {category.get('name')}"

        # Markdown (Frontmatter) の作成
        # このテーマ (Bookworm Light) の形式に合わせる
        md_content = f"""---
title: "{title}"
description: "{description}"
date: {published_at}
categories: {category_json}
draft: false
---

{content}
"""
        
        file_path = os.path.join(output_dir, f"{slug}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        print(f"Synced: {slug}.md")

    print(f"\nDone! Synced {len(contents)} posts.")

if __name__ == "__main__":
    sync()
