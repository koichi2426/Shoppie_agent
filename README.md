# Shoppie\_agent

**Shoppie\_agent**は、音声対話で商品検索ができるショッピングアプリ「Shoppie」における、LangChainベースのエージェント実装です。

---

## 概要

Shoppie\_agentは、ユーザーの発言を自然言語で受け取り、LangChainとClaude 3.5 Haiku（Amazon Bedrock経由）を用いて、適切なツール実行と対話生成を行うエージェントです。楽天APIと連携し、商品情報の取得と応答を自動化します。

---

## システム構成図

![Shoppie Agent Architecture](https://github.com/user-attachments/assets/cd7f62fc-b91e-4e53-be21-2220338c0a2e)

---

## フロー詳細

1. **発話入力（FastAPI）**

   * ユーザーから音声またはテキストの発言を受信。
   * LangChainに渡される。

2. **思考判断（LangChain + Claude 3.5 Haiku）**

   * LLMはMemoryを参照しながら、適切なツールの選択と、必要な入力形式への整形を行い、自動でツールを実行。

3. **ツール実行と繰り返し思考**

   * ツールの実行結果（例：商品リスト）がLLMに渡される。
   * LLMはこれを評価し、返答として「相応しい」と判断されれば、発話情報と商品情報を出力。
   * 相応しくない場合は、Memoryと照らし合わせて思考プロセスを繰り返し、再度ツールを実行または他の手段を検討。

4. **応答生成と出力**

   * 最終的な応答（発話）と商品情報をFastAPIに返却。
   * Memoryに対話履歴が保存され、次回以降の発話判断に活用される。
