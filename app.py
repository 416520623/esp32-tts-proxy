# app.py - TTS 代理服务器
import os
import urllib.parse
import json
import requests
from flask import Flask, request, Response
from aliyunsdkcore.client import AcsClient
from aliyunsdknls.request.v20190924 import GetTokenRequest

app = Flask(__name__)

ACCESS_KEY_ID = os.environ['ACCESS_KEY_ID']
ACCESS_KEY_SECRET = os.environ['ACCESS_KEY_SECRET']
APP_KEY = os.environ['APP_KEY']
REGION = "cn-shanghai"

def get_token():
    client = AcsClient(ACCESS_KEY_ID, ACCESS_KEY_SECRET, REGION)
    req = GetTokenRequest.GetTokenRequest()
    req.set_AppKey(APP_KEY)
    resp = client.do_action_with_exception(req)
    return json.loads(resp)['Token']['Id']

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
