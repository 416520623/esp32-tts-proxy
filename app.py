# app.py - 阿里云 NLS TTS 代理服务（支持 Render 部署）
import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import uuid
import requests
from flask import Flask, request, send_file, jsonify
import tempfile

# 初始化 Flask
app = Flask(__name__)

# 从环境变量读取密钥（在 Render 后台设置）
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
ACCESS_KEY_SECRET = os.getenv("ACCESS_KEY_SECRET")
APP_KEY = os.getenv("APP_KEY")

if not all([ACCESS_KEY_ID, ACCESS_KEY_SECRET, APP_KEY]):
    raise RuntimeError("❌ 缺少环境变量: ACCESS_KEY_ID, ACCESS_KEY_SECRET, APP_KEY")

def percent_encode(s):
    """阿里云要求的 RFC 3986 编码"""
    if isinstance(s, str):
        s = s.encode('utf-8')
    encoded = urllib.parse.quote(s, safe='')
    return encoded.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')

def get_token():
    """获取阿里云 NLS Token"""
    url = "https://nls-meta.cn-shanghai.aliyuncs.com/"
    params = {
        "AccessKeyId": ACCESS_KEY_ID,
        "Action": "CreateToken",
        "AppKey": APP_KEY,
        "Format": "JSON",
        "RegionId": "cn-shanghai",
        "SignatureMethod": "HMAC-SHA1",
        "SignatureVersion": "1.0",
        "SignatureNonce": str(uuid.uuid4()),  # 必须！防止重放攻击
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Version": "2019-02-28"  # Token 接口固定版本
    }

    # 排序并构造签名字符串
    sorted_keys = sorted(params.keys())
    canonical = '&'.join([
        percent_encode(k) + '=' + percent_encode(str(params[k]))
        for k in sorted_keys
    ])
    string_to_sign = 'GET&%2F&' + percent_encode(canonical)

    # 计算签名
    key = (ACCESS_KEY_SECRET + '&').encode('utf-8')
    signature = base64.b64encode(
        hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1).digest()
    ).decode('utf-8')
    params["Signature"] = signature

    # 请求 Token
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        raise Exception(f"获取 Token 失败: {resp.text}")
    
    token_data = resp.json()
    return token_data["Token"]["Id"]

def text_to_speech(text, token):
    """调用阿里云 TTS 流式合成接口"""
    url = "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts"
    
    payload = {
        "appkey": APP_KEY,
        "token": token,
        "text": text,
        "format": "mp3",
        "sample_rate": 16000,
        "voice": "xiaoyun",  # 可选：xiaogang, siyue 等
        "volume": 50,
        "speech_rate": 0,
        "pitch_rate": 0
    }

    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, stream=True)
    
    if resp.status_code != 200:
        raise Exception(f"TTS 合成失败: {resp.text}")
    
    # 将音频流写入临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        for chunk in resp.iter_content(chunk_size=1024):
            if chunk:
                tmp.write(chunk)
        return tmp.name

@app.route("/", methods=["GET"])
def tts_proxy():
    text = request.args.get("text", "").strip()
    if not text:
        return jsonify({"error": "缺少参数: text"}), 400

    try:
        print(f"--- 🎯 Processing TTS request: '{text}' ---")
        
        # 获取 Token
        token = get_token()
        print(f"<<< [DEBUG] Got token: {token[:8]}...")

        # 生成语音
        audio_path = text_to_speech(text, token)
        print("✅ TTS audio generated successfully.")

        # 返回 MP3 文件
        return send_file(audio_path, mimetype="audio/mpeg", as_attachment=False)

    except Exception as e:
        print(f"💥 Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
