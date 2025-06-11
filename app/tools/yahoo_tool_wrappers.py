from langchain_community.tools import tool
from pydantic import BaseModel, Field
from app.tools import yahoo_api
import json

# 🔧 dict型の複雑な検索条件に対応
class YahooFiltersModel(BaseModel):
    price_from: int = Field(..., description="最小価格（円）")
    price_to: int = Field(..., description="最大価格（円）")
    is_discounted: str = Field(..., description="セール品のみ: 'true' または 'false'")
    sort: str = Field(..., description="並び順（例: '-score', '+price'）")

class YahooSearchProductInput(BaseModel):
    keyword: str = Field(..., description="検索キーワード")
    filters: YahooFiltersModel = Field(..., description="検索条件フィルター")

@tool(args_schema=YahooSearchProductInput)
def search_yahoo_products_with_filters_tool(keyword: str, filters: YahooFiltersModel) -> dict:
    """
    Yahoo!ショッピングで条件付き商品検索（最大10件）を行います。
    """
    result_json = yahoo_api.search_products_with_filters(keyword, filters.dict())
    return json.loads(result_json)
