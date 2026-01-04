import firebase_admin
from firebase_admin import credentials, firestore
import datetime

class FirestoreClient:
    def __init__(self, key_path="service_account.json"):
        # 二重初期化防止
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def add_log(self, channel_id, role, text, thread_ts=None):
        """会話ログを保存"""
        data = {
            "channel_id": channel_id,
            "role": role,  # "user" or "model"
            "text": text,
            "thread_ts": thread_ts, # スレッド識別用
            "timestamp": datetime.datetime.now()
        }
        # コレクション: channels > {channel_id} > messages > {auto_id}
        self.db.collection("channels").document(channel_id).collection("messages").add(data)

    def get_context(self, channel_id, thread_ts=None, limit=10):
        """Gemini用に過去ログを取得して整形"""
        # 直近 N 件を取得
        query = self.db.collection("channels").document(channel_id).collection("messages")
        
        if thread_ts:
            query = query.where("thread_ts", "==", thread_ts)
            
        # 最新順に取得してリミットをかける
        docs = query.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
        
        history = []
        for doc in docs:
            d = doc.to_dict()
            history.append({
                "role": d["role"],
                "parts": [d["text"]]
            })
        
        # Geminiには「古い順」で渡す必要があるので反転
        return list(reversed(history))

# テスト用
if __name__ == "__main__":
    client = FirestoreClient()
    # client.add_log("C12345", "user", "こんにちは")
    # print(client.get_context("C12345"))