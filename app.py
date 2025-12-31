# app.py - 阿里云 TTS 代理服务（安全 + 调试版）
import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
from flask import Flask, request, Response

# 从环境变量读取密钥（不要写死在代码中！）
ACCESS_KEY_ID = os.environ['ACCESS_KEY_ID']
ACCESS_KEY_SECRET = os.environ['ACCESS_KEY_SECRET']
APP_KEY = os.environ['APP_KEY']

def percent_encode(s):
    """阿里云要求的严格 URL 编码（RFC 3986）"""
    if isinstance(s, str):
        s = s.encode('utf-8')
    encoded = urllib.parse.quote(s, safe='')
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
        "Version": "2020-03-05"
    }

    # 按字典序排序并构造规范查询字符串
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

    # 发送请求
    print(">>> 请求 Token 接口...")
    resp = requests.get(url, params=params)
    print(f"<<< 响应状态码: {resp.status_code}")
    print(f"<<< 响应内容: {resp.text}")

    if resp.status_code != 200:
        raise Exception(f"Token 请求失败: HTTP {resp.status_code} - {resp.text}")
    
    data = resp.json()
    if "Token" not in data or "Id" not in data["Token"]:
        raise Exception(f"无效的 Token 响应: {data}")
    
    token_id = data["Token"]["Id"]
    print(f"✅ 成功获取 Token: {token_id[:10]}...")  # 只打印前10位
    return token_id

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

    print(f"\n--- 处理 TTS 请求: '{text}' ---")
    
    try:
        token = get_token()
        tts_url = (
            f"https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts?"
            f"appkey={APP_KEY}&token={token}&text={urllib.parse.quote(text)}"
            f"&format=mp3&sample_rate=16000&volume=50"
        )
        print(">>> 请求 TTS 音频流...")
        audio_resp = requests.get(tts_url, stream=True)
        
        if audio_resp.status_code != 200:
            raise Exception(f"TTS 音频请求失败: {audio_resp.status_code} - {audio_resp.text}")
        
        print("✅ 返回 MP3 音频流")
        return Response(audio_resp.iter_content(chunk_size=1024), content_type="audio/mpeg")
    
    except Exception as e:
        error_msg = f"TTS Error: {str(e)}"
        print("❌ 错误:", error_msg)
        return error_msg, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
