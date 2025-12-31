# app.py - 阿里云 TTS 代理服务（最终整合版 + 调试日志）
import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
from flask import Flask, request, Response

# 从环境变量安全读取密钥（不要写死在代码中！）
ACCESS_KEY_ID = os.environ['ACCESS_KEY_ID']
ACCESS_KEY_SECRET = os.environ['ACCESS_KEY_SECRET']
APP_KEY = os.environ['APP_KEY']

def percent_encode(s):
    """阿里云要求的严格 URL 编码（符合 RFC 3986）"""
    if isinstance(s, str):
        s = s.encode('utf-8')
    encoded = urllib.parse.quote(s, safe='')
    # 替换 Python 默认 quote 不符合阿里云规范的字符
    return encoded.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')

def get_token():
    """调用阿里云 NLS 接口获取 Token"""
    url = "https://nls-meta.cn-shanghai.aliyuncs.com/"
    
    params = {
        "AccessKeyId": ACCESS_KEY_ID,
        "Action": "CreateToken",
        "AppKey": APP_KEY,
        "Format": "JSON",
        "RegionId": "cn-shanghai",
        "SignatureMethod": "HMAC-SHA1",
        "SignatureVersion": "1.0",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Version": "2020-03-05"  # ✅ 必须是这个版本！
    }

    # 按字典序排序参数
    sorted_keys = sorted(params.keys())
    canonical = '&'.join([
        percent_encode(k) + '=' + percent_encode(str(params[k]))
        for k in sorted_keys
    ])
    
    # 构造待签名字符串
    string_to_sign = 'GET&%2F&' + percent_encode(canonical)

    # 计算 HMAC-SHA1 签名
    key = (ACCESS_KEY_SECRET + '&').encode('utf-8')
    signature = base64.b64encode(
        hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1).digest()
    ).decode('utf-8')

    params["Signature"] = signature

    # 发送请求并记录调试信息
    print(">>> [DEBUG] Sending request to NLS Token API...")
    resp = requests.get(url, params=params)
    
    print(f"<<< [DEBUG] Token API Status: {resp.status_code}")
    print(f"<<< [DEBUG] Token API Response: {resp.text}")

    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}: {resp.text}")
    
    try:
        data = resp.json()
    except Exception as e:
        raise Exception(f"Failed to parse JSON: {resp.text} | Error: {e}")

    if "Token" not in data or "Id" not in data.get("Token", {}):
        raise Exception(f"Missing 'Token.Id' in response. Full response: {data}")

    token_id = data["Token"]["Id"]
    print(f"✅ [SUCCESS] Token obtained: {token_id[:12]}...")
    return token_id

# 初始化 Flask 应用
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ TTS Proxy is running! Use: /speak?text=你好世界"

@app.route('/speak')
def speak():
    # 获取并解码文本（支持中文）
    text = request.args.get('text', '你好')
    try:
        text = urllib.parse.unquote(text)
    except:
        pass
    text = text[:100]  # 限制长度防止滥用

    print(f"\n--- 🎯 Processing TTS request: '{text}' ---")
    
    try:
        token = get_token()
        tts_url = (
            f"https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts?"
            f"appkey={APP_KEY}&token={token}&text={urllib.parse.quote(text)}"
            f"&format=mp3&sample_rate=16000&volume=50"
        )
        print(">>> [DEBUG] Requesting TTS audio stream...")
        audio_resp = requests.get(tts_url, stream=True)
        
        if audio_resp.status_code != 200:
            raise Exception(f"TTS audio failed: {audio_resp.status_code} - {audio_resp.text}")
        
        print("✅ [SUCCESS] Returning MP3 audio stream")
        return Response(audio_resp.iter_content(chunk_size=1024), content_type="audio/mpeg")
    
    except Exception as e:
        error_msg = f"TTS Error: {str(e)}"
        print("❌ [ERROR]", error_msg)
        return error_msg, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
