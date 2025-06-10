from rakuten_api import (
    search_products,
    keyword_to_ranking_products  # ← 新たに追加
)

def test_all_functions():
    # テスト用のキーワード
    test_keyword = "レディースファッション"

    # print("🔍 商品検索テスト")
    # print(search_products(test_keyword))
    # print("\n" + "="*50 + "\n")

    print("🏆 キーワードからランキング取得テスト")
    print(keyword_to_ranking_products(test_keyword))
    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    test_all_functions()
