# AI Agent Organization for YouTube - 要件定義書

**Version:** 1.1.0  
**Last Updated:** 2026-01-05

## 1. プロジェクト概要
YouTubeチャンネルの新規立ち上げおよび運営（企画・構成・編集指示・分析）を効率化するため、Slack上にGeminiベースの「AIエージェントチーム（組織）」を構築する。
ユーザーはSlackを通じて各専門AIに指示を出すほか、AI同士が自律的に会議を行い、企画のブラッシュアップまでを自動で遂行するシステムを目指す。

## 2. システム構成 (Architecture)

### 2.1 全体構成
* **Interface**: Slack (Chat UI / Socket Mode)
* **Backend**: Python 3 (Slack Bolt Framework)
* **AI Engine**: Google Gemini API (gemini-1.5-flash / pro)
* **Infrastructure**: Oracle Cloud Infrastructure (Always Free Tier / Ubuntu ARM)
* **Deployment**: GitHub Actions (CI/CD via SSH)

### 2.2 ディレクトリ構造
```text
ai-agent/
├── .github/
│   └── workflows/
│       └── deploy.yml      # GitHub Actions 自動デプロイ設定
├── venv/                   # Python仮想環境 (Git対象外)
├── agents.py               # エージェント人格定義・会議室設定
├── main.py                 # アプリケーション本体・ロジック
├── requirements.txt        # 依存ライブラリ一覧
├── .env                    # 環境変数 (Git対象外・Secrets管理)
├── .gitignore              # Git除外設定
└── service_account.json    # GCP認証鍵 (Git対象外・Secrets管理)

### 3. 機能要件

```markdown
## 3. 機能要件 (Functional Requirements)

### 3.1 マルチエージェント・ルーター機能
* Slackの **チャンネルID** に基づき、応答するAI人格（System Prompt）を自動で切り替える。
* メンション (`@bot`) だけでなく、チャンネル内の全ての投稿 (`message` イベント) を検知して応答する。
* **対象チャンネル**:
    * `#01_director_room`: 統括ディレクター
    * `#02_planning_room`: 企画・構成作家
    * `#03_editor_room`: 編集・SEO担当

### 3.2 文脈保持 (Context Awareness)
* Slackのスレッド履歴を取得し、GeminiのChat Session形式 (`user` / `model`) に変換してAPIへ送信する。
* これにより、「さっきの件だけど」等の指示や、以前の会話を踏まえた回答を可能にする。

### 3.3 自律会議モード (Autonomous Brainstorming)
* **トリガー**: 特定の会議用チャンネル（`#00_brainstorming`）への投稿。
* **動作**: ユーザーの投稿（テーマ）を起点に、Pythonプログラムが進行役（Moderator）となり、複数のエージェントを連鎖的に呼び出す。
* **フロー**:
    1.  **Moderator**: 会議開始宣言。
    2.  **Planner**: 案出し（3案提示）。
    3.  **Director**: 批判的レビュー・選定。
    4.  **Editor**: 実現性チェック・SEOキーワード選定。
    5.  **Planner**: 最終構成案の作成・提出。
    6.  **Moderator**: 終了宣言。
* **UI表現**: 各エージェントの発言時、Slackのアイコンとユーザー名を動的に変更し、別人が会話しているように見せる。

## 4. エージェント定義 (Personas)

| 役割 (Role) | 担当機能 | 性格・特徴 |
| :--- | :--- | :--- |
| **統括ディレクター** | クオリティ管理、Go/NoGo判断 | **[鬼軍曹]** 数字（再生数・維持率）至上主義。論理的かつ冷徹。口癖は「甘い」「やり直し」。 |
| **企画・構成作家** | アイデア出し、台本構成 | **[ハイテンション]** 面白さとフック重視。感情豊かでフレンドリー。口癖は「バズりそう！」。 |
| **編集・SEO担当** | 技術指示、サムネ・タイトル選定 | **[冷静なエンジニア]** 技術的実現性とアルゴリズム重視。淡々と箇条書きで回答する。 |
| **Moderator** | 会議進行 (System) | AI同士の会話をつなぐシステム上の進行役。Pythonロジックとして実装。 |

## 5. 技術スタック & 環境

### 5.1 言語・ライブラリ
* **Python 3.12+**
* `slack_bolt`: Slackアプリフレームワーク (Socket Mode)
* `google-generativeai`: Gemini APIクライアント
* `python-dotenv`: 環境変数管理

### 5.2 必要な環境変数 (.env)
* `SLACK_BOT_TOKEN`: Bot User OAuth Token (`xoxb-...`)
* `SLACK_APP_TOKEN`: App-Level Token (`xapp-...`)
* `GEMINI_API_KEY`: Google AI Studio API Key

### 5.3 インフラ & デプロイ
* **Server**: Oracle Cloud Compute (Ubuntu)
* **Process Management**: Systemd (`slack-bot.service`) による常時稼働・自動再起動。
* **CI/CD**: GitHub Actions
    * `main` ブランチへのPushをトリガーに発動。
    * SSH経由でサーバーへ接続し、`git pull` -> `pip install` -> `systemctl restart` を自動実行。
    * **Security**: `.env` や `service_account.json` はGitに含めず、サーバー上に直接配置＆GitHub Secretsで管理。

## 6. 今後の拡張ロードマップ (Future)
1.  **定期実行 (Scheduler)**: 毎朝トレンド情報を自動収集して企画提案させる (`APScheduler`導入)。
2.  **ツール使用 (Function Calling)**: AIが自らGoogle検索やYouTubeアナリティクスAPIを叩けるようにする。
3.  **データベース連携 (Firestore)**: 会話ログの永続化、タスク管理機能の実装。