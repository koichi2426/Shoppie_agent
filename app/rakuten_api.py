import os
import requests

APP_ID = os.getenv("RAKUTEN_APP_ID")

def search_products(keyword: str) -> str:
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = {
        "applicationId": APP_ID,
        "keyword": keyword,
        "format": "json"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json().get("Items", [])
        results = [f"{item['Item']['itemName']} - {item['Item']['itemUrl']}" for item in items[:3]]
        return "\n".join(results) if results else "商品が見つかりませんでした。"
    return "楽天APIからの取得に失敗しました。"
