import os
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import google.generativeai as genai

# エージェント設定を読み込み
from agents import AGENTS_CONFIG, DEFAULT_PROMPT

# 環境変数の読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)

# 初期化
app = App(token=os.environ["SLACK_BOT_TOKEN"])
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Bot自身のユーザーIDを取得（自分の発言をAIに区別させるため）
BOT_ID = app.client.auth_test()["user_id"]

def get_thread_history(channel_id, thread_ts):
    """
    Slackのスレッド履歴を取得し、Gemini用の形式に変換する関数
    """
    try:
        # スレッドのメッセージを取得
        result = app.client.conversations_replies(
            channel=channel_id,
            ts=thread_ts
        )
        messages = result.get("messages", [])
        
        gemini_history = []
        
        for msg in messages:
            text = msg.get("text", "")
            user = msg.get("user")
            
            # Bot自身の発言は 'model'、ユーザーの発言は 'user' とする
            role = "model" if user == BOT_ID else "user"
            
            # Geminiの履歴フォーマットに追加
            gemini_history.append({
                "role": role,
                "parts": [text]
            })
            
        # 最新のメッセージ（今回の入力）は履歴から除外して別途扱うこともできるが、
        # ここでは履歴全体を渡して、最後の発言に対して応答させる形をとる
        return gemini_history
        
    except Exception as e:
        logging.error(f"Error fetching history: {e}")
        return []

@app.event("app_mention")
def handle_mention(event, say):
    """
    メンションされた時の処理（メインロジック）
    """
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"]) # スレッド内ならそのID、新規なら自分のID
    user_text = event["text"]

    logging.info(f"Received message in channel: {channel_id}")

    # 1. Routing: チャンネルIDに基づいてエージェント人格を選択
    agent_config = AGENTS_CONFIG.get(channel_id)
    
    if agent_config:
        system_instruction = agent_config["system_prompt"]
        role_name = agent_config["role"]
        logging.info(f"Agent selected: {role_name}")
    else:
        system_instruction = DEFAULT_PROMPT
        logging.info("Agent selected: Default")

    # 2. Context Fetching: 会話履歴の取得
    # Geminiに渡すための履歴リストを作成
    history = get_thread_history(channel_id, thread_ts)

    # 3. Generation: Gemini API呼び出し
    try:
        # システムプロンプトを設定してモデルを初期化
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash", # または "gemini-1.5-pro"
            system_instruction=system_instruction
        )

        # チャットセッションを開始（履歴付き）
        # historyの最後がユーザーの入力になっているはずなので、それをトリガーにする
        # ただし、APIの仕様上、start_chatに渡すhistoryは「最後の1件（今回の問い）」を含まない過去ログが望ましい場合がある
        # ここではシンプルに `generate_content` に履歴リスト全体を渡すアプローチをとるか、
        # `start_chat` を使う。今回は文脈維持のため `start_chat` を採用。
        
        # historyの末尾（今回のユーザー発言）を取り出す
        current_message = history[-1]['parts'][0]
        past_history = history[:-1] if len(history) > 1 else []

        chat = model.start_chat(history=past_history)
        response = chat.send_message(current_message)
        
        reply_text = response.text

    except Exception as e:
        reply_text = f"申し訳ありません。思考回路にエラーが発生しました。\nError: {str(e)}"
        logging.error(f"Gemini API Error: {e}")

    # 4. Output: 返信
    say(text=reply_text, thread_ts=thread_ts)

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()