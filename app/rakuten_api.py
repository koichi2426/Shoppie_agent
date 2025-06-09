import os
import requests

APP_ID = os.getenv("RAKUTEN_APP_ID")
AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID")

# ✅ 共通パラメータ
def base_params():
    return {
        "applicationId": APP_ID,
        "affiliateId": AFFILIATE_ID,
        "format": "json"
    }

# 🔍 商品検索（キーワード）
def search_products(keyword: str) -> str:
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = base_params()
    params.update({"keyword": keyword})
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json().get("Items", [])
        results = [
            f"{item['Item'].get('itemName', '商品名不明')} - {item['Item'].get('affiliateUrl', 'URLなし')}"
            for item in items[:3]
        ]
        return "\n".join(results) if results else "商品が見つかりませんでした。"
    return "商品検索に失敗しました。"

# 🏆 売れ筋ランキング（ジャンル指定）
def get_ranking(genre_id: str = "100283") -> str:
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
    params = base_params()
    params.update({"genreId": genre_id})
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json().get("Items", [])
        results = [
            f"【{item['Item'].get('rank', '?')}位】{item['Item'].get('itemName', '商品名不明')} - {item['Item'].get('affiliateUrl', 'URLなし')}"
            for item in items[:3]
        ]
        return "\n".join(results) if results else "ランキング情報が見つかりませんでした。"
    return "ランキング取得に失敗しました。"


# 🔍 ジャンル検索（キーワード→最初の候補1件）
def get_genre_id_from_keyword(keyword: str) -> str:
    url = "https://app.rakuten.co.jp/services/api/IchibaGenre/Search/20140222"
    params = base_params()
    params.update({"keyword": keyword})
    response = requests.get(url, params=params)
    if response.status_code == 200:
        genres = response.json().get("children", [])
        if genres:
            first_genre = genres[0]["child"]
            genre_name = first_genre.get("genreName", "不明ジャンル")
            genre_id = first_genre.get("genreId", "")
            return genre_id
    return None

# 🎯 統合ツール：キーワードから売れ筋を取得
def keyword_to_ranking(keyword: str) -> str:
    genre_id = get_genre_id_from_keyword(keyword)
    if genre_id:
        return get_ranking(genre_id)
    return "該当ジャンルが見つかりませんでした。"

# 🆕 新着順の商品取得（キーワード）
def get_new_arrivals(keyword: str) -> str:
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = base_params()
    params.update({
        "keyword": keyword,
        "sort": "-updateTimestamp"  # 新着順
    })
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json().get("Items", [])
        results = [
            f"{item['Item'].get('itemName', '商品名不明')}（更新: {item['Item'].get('updateTimestamp', '不明')}） - {item['Item'].get('affiliateUrl', 'URLなし')}"
            for item in items[:3]
        ]
        return "\n".join(results) if results else "新着商品が見つかりませんでした。"
    return "新着商品の取得に失敗しました。"

# 💰 最安値商品を探す（キーワード）
def get_lowest_price(keyword: str) -> str:
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = base_params()
    params.update({
        "keyword": keyword,
        "sort": "+itemPrice"  # 価格昇順
    })
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json().get("Items", [])
        if not items:
            return "最安値の商品が見つかりませんでした。"
        item = items[0]["Item"]
        return f"最安値: {item.get('itemName', '商品名不明')}（{item.get('itemPrice', '?')}円） - {item.get('affiliateUrl', 'URLなし')}"
    return "価格情報の取得に失敗しました。"

# 📝 商品詳細情報を取得（itemCode指定）
def get_product_detail(item_code: str) -> str:
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = base_params()
    params.update({"itemCode": item_code})
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json().get("Items", [])
        if not items:
            return "商品詳細が見つかりませんでした。"
        item = items[0]["Item"]
        return (
            f"{item.get('itemName', '商品名不明')}\n"
            f"価格: {item.get('itemPrice', '?')}円\n"
            f"説明: {item.get('itemCaption', '説明なし')}\n"
            f"URL: {item.get('affiliateUrl', 'URLなし')}"
        )
    return "商品詳細の取得に失敗しました。"
