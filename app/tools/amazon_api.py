import os
from amazon_paapi import AmazonApi

# ✅ 環境変数から認証情報を読み込む
ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")
COUNTRY = "JP"  # 日本版APIを使用

# ✅ Amazon API クライアント初期化
amazon = AmazonApi(ACCESS_KEY, SECRET_KEY, ASSOCIATE_TAG, COUNTRY)

# 🔍 商品検索（キーワード）
def search_products(keyword: str) -> str:
    results = amazon.search_items(keywords=keyword, search_index="All", item_count=3)
    if not results.items:
        return "商品が見つかりませんでした。"
    return "\n".join([f"{item.title} - {item.detail_page_url}" for item in results.items])

# 🆕 新着順の商品取得
def get_new_arrivals(keyword: str) -> str:
    results = amazon.search_items(keywords=keyword, search_index="All", item_count=3, sort_by="NewestArrivals")
    if not results.items:
        return "新着商品が見つかりませんでした。"
    return "\n".join([f"{item.title} - {item.detail_page_url}" for item in results.items])

# 💰 最安値商品を探す
def get_lowest_price(keyword: str) -> str:
    results = amazon.search_items(keywords=keyword, search_index="All", item_count=1, sort_by="Price:LowToHigh")
    if not results.items:
        return "最安値の商品が見つかりませんでした。"
    item = results.items[0]
    return f"最安値: {item.title} - {item.detail_page_url}"

# 🏆 売れ筋ランキング（代用：Featured順）
def get_ranking(keyword: str) -> str:
    results = amazon.search_items(keywords=keyword, search_index="All", item_count=3, sort_by="Featured")
    if not results.items:
        return "ランキング情報が見つかりませんでした。"
    return "\n".join([f"{item.title} - {item.detail_page_url}" for item in results.items])

# 📝 商品詳細情報を取得（ASIN指定）
def get_product_detail(asin: str) -> str:
    result = amazon.get_items(asin)
    if not result.items:
        return "商品詳細が見つかりませんでした。"
    item = result.items[0]
    return (
        f"{item.title}\n"
        f"商品URL: {item.detail_page_url}\n"
        f"価格: {item.list_price or '不明'}"
    )
