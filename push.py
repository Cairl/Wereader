import os
import time
import json
import logging
import requests
import urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

class PushNotification:
    def __init__(self):
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.headers = {'Content-Type': 'application/json'}

    def _post(self, url, data=None, json_data=None, timeout=10):
        try:
            resp = self.session.post(url, data=data, json=json_data, headers=self.headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.error(f"❌ Request failed: {e}")
            raise

    def push_pushplus(self, content, token):
        if not token:
            logger.warning("[消息推送] PUSHPLUS: 缺少 TOKEN")
            return
        
        url = "https://www.pushplus.plus/send"
        data = {
            "token": token,
            "title": "WeRead 自动阅读通知",
            "content": content,
            "template": "html"
        }
        try:
            resp = self._post(url, json_data=data)
            logger.info(f"[消息推送] PUSHPLUS: 成功 | 响应: {resp.text}")
        except Exception:
            logger.error("[消息推送] PUSHPLUS: 失败")

    def push_telegram(self, content, bot_token, chat_id):
        if not bot_token or not chat_id:
            logger.warning("[消息推送] TELEGRAM: 配置缺失")
            return

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": content}
        
        proxies = {
            'http': os.getenv('http_proxy'),
            'https': os.getenv('https_proxy')
        }
        
        try:
            resp = self.session.post(url, json=payload, proxies=proxies, timeout=15)
            resp.raise_for_status()
            logger.info(f"[消息推送] TELEGRAM: 成功 | 响应: {resp.text}")
        except Exception as e:
            logger.error(f"[消息推送] TELEGRAM: 失败 | 错误: {e}")

    def push_wxpusher(self, content, spt):
        if not spt:
            logger.warning("[消息推送] WXPUSHER: 缺少 SPT 配置")
            return
            
        safe_content = urllib.parse.quote(content)
        url = f"https://wxpusher.zjiecode.com/api/send/message/{spt}/{safe_content}"
        
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            logger.info(f"[消息推送] WXPUSHER: 成功 | 响应: {resp.text}")
        except Exception as e:
            logger.error(f"[消息推送] WXPUSHER: 失败 | 错误: {e}")

    def push_serverChan(self, content, send_key):
        if not send_key:
            logger.warning("[消息推送] SERVERCHAN: 缺少 KEY")
            return

        url = f"https://sctapi.ftqq.com/{send_key}.send"
        title = "WeRead 自动阅读通知"
        if "失败" in content or "错误" in content:
            title = "WeRead 自动阅读异常"
            
        data = {"title": title, "desp": content}
        
        try:
            resp = self._post(url, json_data=data)
            logger.info(f"[消息推送] SERVERCHAN: 成功 | 响应: {resp.text}")
        except Exception:
            logger.error("[消息推送] SERVERCHAN: 失败")

def push(content, config):
    """
    自动检测配置并执行推送。
    """
    notifier = PushNotification()
    triggered = False

    # PushPlus
    if config.get("PUSH_PUSHPLUS_TOKEN"):
        notifier.push_pushplus(content, config.get("PUSH_PUSHPLUS_TOKEN"))
        triggered = True
    
    # Telegram
    if config.get("PUSH_TELEGRAM_TOKEN") and config.get("PUSH_TELEGRAM_CHAT_ID"):
        notifier.push_telegram(content, config.get("PUSH_TELEGRAM_TOKEN"), config.get("PUSH_TELEGRAM_CHAT_ID"))
        triggered = True

    # WxPusher
    if config.get("PUSH_WXPUSHER_TOKEN"):
        notifier.push_wxpusher(content, config.get("PUSH_WXPUSHER_TOKEN"))
        triggered = True

    # ServerChan
    if config.get("PUSH_SERVERCHAN_SENDKEY"):
        notifier.push_serverChan(content, config.get("PUSH_SERVERCHAN_SENDKEY"))
        triggered = True

    if not triggered:
        logger.info("[消息推送] ℹ️ 未检测到任何推送配置，跳过通知")
