import os
import time
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import google.generativeai as genai

# 設定読み込み
from agents import AGENTS_CONFIG, AGENT_PROFILES, BRAINSTORMING_CHANNEL_ID, DEFAULT_PROMPT

# 環境変数の読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)

# 初期化
app = App(token=os.environ["SLACK_BOT_TOKEN"])
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Bot自身のID
BOT_ID = app.client.auth_test()["user_id"]


# ==========================================
# 共通関数：Geminiを呼び出す
# ==========================================
def call_gemini(system_prompt, user_text):
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_prompt
        )
        response = model.generate_content(user_text)
        return response.text
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return f"エラーが発生しました: {str(e)}"

# ==========================================
# 共通関数：エージェントになりすまして投稿
# ==========================================
def post_as_agent(channel_id, thread_ts, text, role_key):
    profile = AGENT_PROFILES.get(role_key, AGENT_PROFILES["Moderator"])
    try:
        app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=text,
            username=profile["name"],   # 名前を偽装
            icon_emoji=profile["icon"]  # アイコンを偽装
        )
    except Exception as e:
        logging.error(f"Post Error: {e}")


# ==========================================
# ★新機能：自律会議システム
# ==========================================
def run_brainstorming_session(channel_id, thread_ts, topic):
    """
    指定されたトピックについて、3人のエージェントが順に発言する
    """
    logging.info(f"Starting brainstorming session for: {topic}")

    # 1. 進行役の開始宣言
    post_as_agent(channel_id, thread_ts, f"これより会議を始めます。\n議題：「{topic}」について", "Moderator")
    time.sleep(2)

    # 2. [作家] 案出しターン
    prompt_1 = f"議題「{topic}」について、YouTubeの企画案を3つ出してください。視聴者の興味を惹くタイトルも含めてください。"
    res_1 = call_gemini(AGENT_PROFILES["Planner"]["prompt"], prompt_1)
    post_as_agent(channel_id, thread_ts, res_1, "Planner")
    time.sleep(3)

    # 3. [鬼D] 批判ターン
    prompt_2 = f"以下の企画案に対して、再生数が伸びないリスクや甘い点を厳しく指摘し、最もマシな案を1つ選んでください。\n\n{res_1}"
    res_2 = call_gemini(AGENT_PROFILES["Director"]["prompt"], prompt_2)
    post_as_agent(channel_id, thread_ts, res_2, "Director")
    time.sleep(3)

    # 4. [編集] 実現性チェック & SEOターン
    prompt_3 = f"ディレクターが選んだ案について、撮影・編集の懸念点と、狙うべきSEOキーワードを提案してください。\n\nディレクターの意見：{res_2}"
    res_3 = call_gemini(AGENT_PROFILES["Editor"]["prompt"], prompt_3)
    post_as_agent(channel_id, thread_ts, res_3, "Editor")
    time.sleep(3)

    # 5. [作家] 最終まとめターン
    prompt_4 = f"これまでの議論を踏まえて、最終的な「動画の構成案（タイトル・サムネ・冒頭の流れ）」をまとめて提出してください。\n\n編集の意見：{res_3}"
    res_4 = call_gemini(AGENT_PROFILES["Planner"]["prompt"], prompt_4)
    post_as_agent(channel_id, thread_ts, f"承知しました！最終決定案はこちらです！！\n\n{res_4}", "Planner")

    # 終了宣言
    post_as_agent(channel_id, thread_ts, "会議終了。お疲れ様でした。", "Moderator")


# ==========================================
# イベントハンドラ
# ==========================================
@app.event("message")
def handle_message(event, say):
    # Bot自身の発言や編集イベントは無視
    if event.get("bot_id") or event.get("subtype"):
        return

    channel_id = event["channel"]
    text = event.get("text", "")
    thread_ts = event.get("thread_ts", event["ts"])

    # パターンA：会議室チャンネルでの発言なら「会議」を開始
    if channel_id == BRAINSTORMING_CHANNEL_ID:
        run_brainstorming_session(channel_id, thread_ts, text)
        return

    # パターンB：それ以外のチャンネルなら「個別の役割」で返信
    agent_config = AGENTS_CONFIG.get(channel_id)
    if agent_config:
        # 通常の1往復の会話
        response = call_gemini(agent_config["system_prompt"], text)
        say(text=response, thread_ts=thread_ts)
    else:
        # 担当がいないチャンネルは無視（ログだけ出す）
        logging.info("No agent assigned to this channel.")

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
