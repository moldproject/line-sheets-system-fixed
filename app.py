import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage
import gspread
from google.oauth2.service_account import Credentials

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 環境変数から設定を取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GOOGLE_SPREADSHEET_ID = os.environ.get('GOOGLE_SPREADSHEET_ID')
GOOGLE_SHEET_NAME = os.environ.get('GOOGLE_SHEET_NAME', 'Sheet1')

# Google認証情報をJSONとして取得
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON')

# LINE Bot API初期化
line_bot_api = None
handler = None
sheets_client = None

def initialize_line_bot():
    """LINE Bot APIを初期化"""
    global line_bot_api, handler
    try:
        if LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET:
            line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
            handler = WebhookHandler(LINE_CHANNEL_SECRET)
            logger.info("LINE Bot API initialized successfully")
            return True
        else:
            logger.error("LINE credentials not found")
            return False
    except Exception as e:
        logger.error(f"Failed to initialize LINE Bot API: {e}")
        return False

def initialize_google_sheets():
    """Google Sheets APIを初期化"""
    global sheets_client
    try:
        if GOOGLE_CREDENTIALS_JSON:
            # JSON文字列をパース
            credentials_info = json.loads(GOOGLE_CREDENTIALS_JSON)
            
            # 必要なスコープを設定
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # 認証情報を作成
            credentials = Credentials.from_service_account_info(
                credentials_info, scopes=scopes
            )
            
            # gspreadクライアントを初期化
            sheets_client = gspread.authorize(credentials)
            logger.info("Google Sheets API initialized successfully")
            return True
        else:
            logger.error("Google credentials not found")
            return False
    except Exception as e:
        logger.error(f"Failed to initialize Google Sheets API: {e}")
        return False

def write_to_sheet(user_id, display_name, message_text):
    """スプレッドシートにデータを書き込み"""
    try:
        if not sheets_client:
            logger.error("Google Sheets client not initialized")
            return False
            
        # スプレッドシートを開く
        spreadsheet = sheets_client.open_by_key(GOOGLE_SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(GOOGLE_SHEET_NAME)
        
        # 現在の日時を取得
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # データを追加
        row_data = [timestamp, user_id, display_name, message_text]
        worksheet.append_row(row_data)
        
        logger.info(f"Data written to sheet: {row_data}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write to sheet: {e}")
        return False

@app.route('/')
def home():
    """ホームページ"""
    return jsonify({
        "message": "LINE to Sheets System is running on Render.com",
        "status": "ok",
        "line_configured": line_bot_api is not None,
        "sheets_configured": sheets_client is not None
    })

@app.route('/health')
def health():
    """ヘルスチェック"""
    return jsonify({"status": "healthy"})

@app.route('/webhook', methods=['POST'])
def webhook():
    """LINE Webhookエンドポイント"""
    try:
        # シグネチャを検証
        signature = request.headers.get('X-Line-Signature', '')
        body = request.get_data(as_text=True)
        
        if not handler:
            logger.error("LINE handler not initialized")
            return 'LINE handler not initialized', 500
            
        handler.handle(body, signature)
        return 'OK', 200
        
    except InvalidSignatureError:
        logger.error("Invalid signature")
        return 'Invalid signature', 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Internal server error', 500

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """テキストメッセージを処理"""
    try:
        # ユーザー情報を取得
        user_id = event.source.user_id
        
        # プロフィール情報を取得（可能な場合）
        try:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
        except:
            display_name = "Unknown User"
        
        # メッセージテキストを取得
        message_text = event.message.text
        
        # スプレッドシートに書き込み
        success = write_to_sheet(user_id, display_name, message_text)
        
        if success:
            logger.info(f"Message processed successfully: {message_text}")
        else:
            logger.error(f"Failed to process message: {message_text}")
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")

# アプリケーション初期化
if __name__ == '__main__':
    # 初期化を実行
    line_initialized = initialize_line_bot()
    sheets_initialized = initialize_google_sheets()
    
    if line_initialized:
        logger.info("✅ LINE Bot API: Initialized")
    else:
        logger.warning("❌ LINE Bot API: Failed to initialize")
        
    if sheets_initialized:
        logger.info("✅ Google Sheets API: Initialized")
    else:
        logger.warning("❌ Google Sheets API: Failed to initialize")
    
    # Flaskアプリを起動
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Gunicorn起動時の初期化
    line_initialized = initialize_line_bot()
    sheets_initialized = initialize_google_sheets()
