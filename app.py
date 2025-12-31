# app.py - 纯 HTTP 实现阿里云 TTS 代理
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

def get_token():
    # 阿里云 NLS Token 接口地址
    url = "https://nls-meta.cn-shanghai.aliyuncs.com/"
    
    # 构造公共参数
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

    # 对参数按字典序排序并拼接
    canonical = "&".join([
        urllib.parse.quote(k, safe='') + "=" + urllib.parse.quote(str(v), safe='')
        for k, v in sorted(params.items())
    ])
    
    # 构造待签名字符串
    string_to_sign = f"GET&%2F&{urllib.parse.quote(canonical, safe='')}"
    
    # 计算 HMAC-SHA1 签名
    key = (ACCESS_KEY_SECRET + "&").encode()
    signature = base64.b64encode(
        hmac.new(key, string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()

    params["Signature"] = signature
    resp = requests.get(url, params=params)
    return resp.json()["Token"]["Id"]

@app.route('/speak')
def speak():
    text = request.args.get('text', '你好')
    text = urllib.parse.unquote(text)[:100]  # 防止滥用
    
    try:
        token = get_token()
        tts_url = (
            f"https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts?"
            f"appkey={APP_KEY}&token={token}&text={urllib.parse.quote(text)}"
            f"&format=mp3&sample_rate=16000&volume=50"
        )
        audio_resp = requests.get(tts_url, stream=True)
        return Response(audio_resp.iter_content(1024), content_type="audio/mpeg")
    except Exception as e:
        print("Error:", e)
        return "TTS Error", 500

@app.route('/')
def home():
    return "✅ TTS Proxy is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
