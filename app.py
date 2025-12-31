# app.py - 纯 HTTP 版 TTS 代理（无需 nls SDK）
import os
import urllib.parse
import json
import time
import hmac
import hashlib
import base64
import requests
from flask import Flask, request, Response

app = Flask(__name__)

ACCESS_KEY_ID = os.environ['ACCESS_KEY_ID']
ACCESS_KEY_SECRET = os.environ['ACCESS_KEY_SECRET']
APP_KEY = os.environ['APP_KEY']
REGION = "cn-shanghai"

def get_token():
    # 构造请求参数
    params = {
        "AccessKeyId": ACCESS_KEY_ID,
        "Action": "CreateToken",
        "AppKey": APP_KEY,
        "Format": "JSON",
        "RegionId": REGION,
        "SignatureMethod": "HMAC-SHA1",
        "SignatureVersion": "1.0",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Version": "2019-09-24"
    }

    # 排序并构造待签名字符串
    sorted_keys = sorted(params.keys())
    canonicalized_query = "&".join([
        urllib.parse.quote(k, safe='') + "=" + urllib.parse.quote(str(params[k]), safe='')
        for k in sorted_keys
    ])
    string_to_sign = "GET&%2F&" + urllib.parse.quote(canonicalized_query, safe='')

    # 计算签名
    key = (ACCESS_KEY_SECRET + "&").encode('utf-8')
    signature = base64.b64encode(hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1).digest()).decode('utf-8')
    params["Signature"] = signature

    # 发送请求
    url = "https://nls-meta.cn-shanghai.aliyuncs.com/"
    resp = requests.get(url, params=params)
    data = resp.json()
    return data["Token"]["Id"]

@app.route('/speak')
def speak():
    text = request.args.get('text', '')
    text = urllib.parse.unquote(text)[:100]
    
    try:
        token = get_token()
        url = (
            f"https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts?"
            f"appkey={APP_KEY}&token={token}&text={urllib.parse.quote(text)}"
            f"&format=mp3&sample_rate=16000&volume=50"
        )
        resp = requests.get(url, stream=True)
        return Response(resp.iter_content(chunk_size=1024), content_type="audio/mpeg")
    except Exception as e:
        print("TTS Error:", str(e))
        return "TTS Error", 500

@app.route('/')
def home():
    return "✅ TTS Proxy is running. Use: /speak?text=你好"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
