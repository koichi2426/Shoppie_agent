import os
import requests
import json

APP_ID = os.getenv("YAHOO_APP_ID")
AFFILIATE_ID = os.getenv("YAHOO_AFFILIATE_ID")

# ✅ 共通パラメータ
def base_params():
    params = {
        "appid": APP_ID,
        "results": 50,
        "in_stock": "true",
        "image_size": 600  # ✅ 大きな画像を取得する指定を追加
    }
    if AFFILIATE_ID:
        params["affiliate_type"] = "vc"
        params["affiliate_id"] = AFFILIATE_ID
    return params

# 🔍 条件付き商品検索（キーワード → 商品情報を50件）
def search_products_with_filters(keyword: str, filters: dict) -> str:
    url = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
    params = base_params()
    params.update({
        "query": keyword
    })
    params.update(filters)  # 🔍 追加条件を反映

    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json().get("hits", [])
        results = []
        for item in items:
            results.append({
                "title": item.get("name", "商品名不明"),
                "url": item.get("url", "URLなし"),
                "image": item.get("exImage", {}).get("url", "画像なし"),  # ✅ medium → exImage.url に変更
                "price": str(item.get("price", "不明")),
                "description": item.get("description", "説明なし")
            })
        return json.dumps(results, ensure_ascii=False, indent=2) if results else json.dumps({"message": "商品が見つかりませんでした。"}, ensure_ascii=False)
    return json.dumps({"error": "商品検索に失敗しました。"}, ensure_ascii=False)
