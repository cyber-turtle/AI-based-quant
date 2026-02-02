import requests
import logging
import os
from threading import Thread

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, bot_token=None):
        self.bot_token = bot_token or "8395921588:AAFuvDgx7bsI6jltukIkSO3N8XO4Y8S-vNQ"
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
    def send_message(self, chat_id, text, parse_mode="Markdown"):
        """Send message via a background thread to not block the main loop"""
        if not chat_id:
            logger.warning("Telegram: No chat_id provided")
            return
            
        def _send():
            try:
                url = f"{self.api_url}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                }
                res = requests.post(url, json=payload, timeout=10)
                if res.status_code == 200:
                    logger.info(f"Telegram message sent to {chat_id}")
                else:
                    logger.error(f"Telegram send failed: {res.text}")
            except Exception as e:
                logger.error(f"Telegram service error: {e}")
                
        Thread(target=_send, daemon=True).start()

    def notify_trade_opened(self, chat_id, symbol, action, price, sl, tp, reason):
        emoji = "🟢" if action == "BUY" else "🔴"
        text = (
            f"{emoji} *TRADE OPENED*\n\n"
            f"📈 *Symbol:* {symbol}\n"
            f"🎯 *Action:* {action}\n"
            f"💵 *Price:* {price}\n"
            f"🛡️ *SL:* {sl}\n"
            f"🎯 *TP:* {tp}\n\n"
            f"🧠 *Reason:* _{reason}_"
        )
        self.send_message(chat_id, text)

    def notify_news_block(self, chat_id, symbol, event):
        text = (
            f"📰 *TRADE BLOCKED (NEWS)*\n\n"
            f"📈 *Symbol:* {symbol}\n"
            f"⚠️ *Event:* {event}\n"
            f"🕒 High-impact news detected. Trading paused."
        )
        self.send_message(chat_id, text)

# Singleton
telegram_service = TelegramService()
