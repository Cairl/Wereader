import os
import re
import sys
import json
import time
import random
import logging
import hashlib
import requests
import urllib.parse
from push import push
import config

# Avoid Windows console GBK emoji errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 配置日志输出
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 常量定义
KEY = "3c5c8717f3daf09iop3423zafeqoi"
READ_URL = "https://weread.qq.com/web/book/read"
RENEW_URL = "https://weread.qq.com/web/login/renewal"

def parse_curl(curl_command):
    """解析 cURL 字符串，增强健壮性"""
    if not curl_command: return {}, {}
    headers, cookies = {}, {}
    
    # 清理换行符和反斜杠
    curl_command = curl_command.replace('\\\n', ' ').replace('\n', ' ')
    
    # 提取 Headers
    for match in re.findall(r"-H '([^:]+): ([^']+?)'", curl_command):
        headers[match[0]] = match[1]
    # 提取 Cookies (-b 或 -H 'Cookie: ...')
    cookie_str = ""
    cookie_match = re.search(r"-b '([^']+)'", curl_command)
    if cookie_match:
        cookie_str = cookie_match.group(1)
    else:
        for k, v in list(headers.items()):
            if k.lower() == 'cookie':
                cookie_str = v
                break
                
    if cookie_str:
        for item in cookie_str.split(';'):
            if '=' in item:
                k, v = item.split('=', 1)
                cookies[k.strip()] = v.strip()
                
    headers = {k: v for k, v in headers.items() if k.lower() != 'cookie'}
    return headers, cookies

def encode_data(data):
    """数据编码"""
    return '&'.join(f"{k}={urllib.parse.quote(str(data[k]), safe='')}" for k in sorted(data.keys()))

def cal_hash(input_string):
    """计算签名"""
    _7032f5, _cc1055 = 0x15051505, 0x15051505
    length = len(input_string)
    _19094e = length - 1
    while _19094e > 0:
        _7032f5 = 0x7fffffff & (_7032f5 ^ ord(input_string[_19094e]) << (length - _19094e) % 30)
        _cc1055 = 0x7fffffff & (_cc1055 ^ ord(input_string[_19094e - 1]) << _19094e % 30)
        _19094e -= 2
    return hex(_7032f5 + _cc1055)[2:].lower()

def get_wr_skey(headers, cookies):
    """刷新会话凭证"""
    try:
        # 构建 Cookie 字符串，使用分号分隔
        cookie_parts = []
        for k, v in cookies.items():
            if v:  # 只添加有值的 cookie
                cookie_parts.append(f"{k}={v}")
        cookie_str = "; ".join(cookie_parts)
        
        logger.debug(f"[身份认证] 🔐 刷新请求 Cookie: {len(cookie_str)} 字符")
        
        # 复制 headers 并添加 Cookie
        req_headers = dict(headers)
        req_headers['Cookie'] = cookie_str
        
        resp = requests.post(
            RENEW_URL, headers=req_headers,
            data=json.dumps({"rq": "%2Fweb%2Fbook%2Fread", "ql": True}, separators=(',', ':')),
            timeout=10
        )
        
        # 解析响应，但不记录敏感信息
        res_json = resp.json()
        if res_json.get('errCode') == -2013:
            logger.warning("[身份认证] ⚠️ 鉴权失败，凭证可能已过期")
        elif res_json.get('succ') == 1:
            logger.info("[身份认证] ✅ 会话刷新成功")
        else:
            logger.warning(f"[身份认证] ⚠️ 会话刷新失败: {res_json.get('errMsg', '未知错误')}")
        
        # 解析 Set-Cookie 头 (可能是多个，用逗号分隔)
        set_cookie = resp.headers.get('Set-Cookie', '')
        if not set_cookie:
            return None
        
        # 处理多个 Set-Cookie 的情况（用逗号或分号分隔）
        combined_cookie = set_cookie.replace(',', ';')
        
        new_cookies = {}
        for part in combined_cookie.split(';'):
            part = part.strip()
            if '=' in part:
                name, value = part.split('=', 1)
                name = name.strip()
                value = value.strip()
                # 检查是否是目标 cookie 且值非空
                if name in ['wr_vid', 'wr_skey', 'wr_rt'] and value:
                    new_cookies[name] = value
        
        if new_cookies:
            return new_cookies
    except Exception as e:
        logger.warning(f"[身份认证] ⚠️ 会话刷新异常: {e}")
    return None


def main():
    # 1. 初始化
    curl_bash = os.getenv('WXREAD_CURL_BASH')
    if not curl_bash:
        logger.error("[系统启动] ❌ 环境变量 WXREAD_CURL_BASH 未配置")
        sys.exit(1)

    # 1. 初始化参数
    try:
        read_minutes_env = os.getenv('READ_MINUTES')
        target_minutes = int(read_minutes_env) if read_minutes_env else 60
    except ValueError:
        logger.warning("[系统配置] ⚠️ READ_MINUTES 格式错误，使用默认值 60")
        target_minutes = 60
    
    sleep_interval = 30 # 固定为 30 秒，这是微信读书统计时长的最稳妥心跳间隔
    
    total_cycles = (target_minutes * 60) // sleep_interval
    if total_cycles < 1: total_cycles = 1

    push_config = {
        "PUSH_PUSHPLUS_TOKEN": os.getenv("PUSH_PUSHPLUS_TOKEN"),
        "PUSH_TELEGRAM_TOKEN": os.getenv("PUSH_TELEGRAM_TOKEN"),
        "PUSH_TELEGRAM_CHAT_ID": os.getenv("PUSH_TELEGRAM_CHAT_ID"),
        "PUSH_WXPUSHER_TOKEN": os.getenv("PUSH_WXPUSHER_TOKEN"),
        "PUSH_SERVERCHAN_SENDKEY": os.getenv("PUSH_SERVERCHAN_SENDKEY")
    }

    # 2. 身份验证
    headers, cookies = parse_curl(curl_bash)
    for k, v in config.DEFAULT_HEADERS.items():
        if k not in headers: headers[k] = v

    logger.info("[身份认证] 🍪 开始验证会话有效性...")
    
    # 检查原始凭证是否有效
    original_vid = cookies.get('wr_vid', '')
    original_skey = cookies.get('wr_skey', '')
    original_rt = cookies.get('wr_rt', '')
    
    has_valid_creds = bool(original_vid and original_skey and original_rt)
    
    if has_valid_creds:
        # 原始凭证有效，直接使用，不调用刷新接口
        logger.info("[身份认证] ✅ 原始凭证有效，直接使用")
    else:
        # 凭证缺失，尝试刷新
        logger.info("[身份认证] ⚠️ 原始凭证不完整，尝试刷新...")
        new_cookies = get_wr_skey(headers, cookies)
        if new_cookies and all(new_cookies.values()):  # 只有当刷新返回有效凭证时才更新
            for k, v in new_cookies.items():
                cookies[k] = v
            logger.info("[身份认证] ✅ 会话刷新成功")
        else:
            logger.warning("[身份认证] ⚠️ 会话刷新失败，保留原始 Cookie 继续执行")

    # 3. 核心循环
    data = config.DATA_TEMPLATE.copy()
    success_count, fail_count = 0, 0
    width = len(str(total_cycles))
    
    logger.info(f"[任务配置] 🚀 目标时长: {target_minutes} 分钟 (预计心跳: {total_cycles} 次 | 间隔: {sleep_interval} 秒)")

    for i in range(1, total_cycles + 1):
        try:
            if 's' in data: data.pop('s')
            data.update({
                'b': random.choice(config.BOOKS),
                'c': random.choice(config.CHAPTERS),
                'ct': int(time.time()),
                'ts': int(time.time() * 1000) + random.randint(0, 1000),
                'rn': random.randint(0, 1000)
            })
            data['sg'] = hashlib.sha256(f"{data['ts']}{data['rn']}{KEY}".encode()).hexdigest()
            data['s'] = cal_hash(encode_data(data))

            resp = requests.post(
                READ_URL, headers=headers, cookies=cookies, 
                data=json.dumps(data, separators=(',', ':')), timeout=10
            )
            res_json = resp.json()

            if res_json.get('succ') == 1:
                success_count += 1
                fail_count = 0
                elapsed_minutes = (i * sleep_interval) / 60
                logger.info(f"[阅读进度] 📖 进度: {i:{width}d}/{total_cycles} | ✅ 成功 | 实际阅读: {elapsed_minutes:4.1f} 分钟")
                if i < total_cycles:
                    logger.info(f"[系统休眠] ⏱️ 正在等待 {sleep_interval} 秒...")
                    time.sleep(sleep_interval)
            else:
                fail_count += 1
                logger.warning(f"[阅读进度] 📖 进度: {i:{width}d}/{total_cycles} | ❌ 异常 | 响应: {res_json}")
                
                if any(k in str(res_json) for k in ['login', 'auth', '登录', '失效']):
                    logger.info("[身份认证] 🔄 尝试自动修复会话...")
                    recovered_cookies = get_wr_skey(headers, cookies)
                    if recovered_cookies:
                        for k, v in recovered_cookies.items():
                            cookies[k] = v
                        logger.info("[身份认证] ✅ 会话修复成功")
                    else:
                        logger.error("[身份认证] ❌ 会话修复失败")

                if fail_count >= 3:
                    logger.error("[任务终止] ❌ 连续失败次数达到上限，强制退出")
                    break
                time.sleep(10)

        except Exception as e:
            fail_count += 1
            logger.error(f"[系统错误] ⚠️ 循环异常: {e}")
            if fail_count >= 3: break
            time.sleep(10)

    # 4. 结算
    final_minutes = (success_count * sleep_interval) / 60
    final_msg = f"微信读书任务完成 | 实际阅读: {final_minutes:.1f} 分钟 | 目标: {target_minutes} 分钟"
    logger.info(f"[任务结算] 🎉 {final_msg}")
    
    push(final_msg, push_config)

    # 5. 退出控制
    if success_count == 0 or fail_count >= 3:
        logger.error("[执行状态] ❌ 任务未达标，标记为失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
