from flask import Flask, request, jsonify, render_template, redirect, session, send_from_directory
import openai
import os
import uuid
from oauthlib.oauth2 import WebApplicationClient
import requests
from langdetect import detect

# Config from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = os.environ.get(
    "GOOGLE_DISCOVERY_URL",
    "https://accounts.google.com/.well-known/openid-configuration"
)
SECRET_KEY = os.environ.get("SECRET_KEY", "megabenysecret")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")

# Flask setup
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# OpenAI setup
openai.api_key = OPENAI_API_KEY

# In-memory chat history
chat_history = []

# Google OAuth client
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# Healthcheck endpoint for Railway
@app.route("/health")
def health():
    return "OK", 200  # This tells Railway the app is live

# ROUTES
@app.route("/")
def home():
    user = session.get("user")
    return render_template("index.html", user=user)

# Chat route
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    msg = data.get("message")
    if not msg:
        return jsonify({"reply": "Message empty"})

    chat_history.append(("user", msg))
    try:
        lang = detect(msg)
    except:
        lang = "sw"

    system_prompt = (
        "Wewe ni Megabeny AI, msaidizi mahiri. "
        "Unamkaribisha kila mtumiaji mpya kwa kusema: 'Karibu Megabeny AI kwa huduma bora'. "
        "Unatoa msaada wa haraka na wa vitendo."
    )
    if lang.startswith("en"):
        system_prompt = (
            "You are Megabeny AI, a skilled assistant. "
            "Greet every user with 'Welcome to Megabeny AI for excellent service'. "
            "Provide fast and practical support."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": msg}
    ]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-5",
            messages=messages
        )
        reply = response['choices'][0]['message']['content']
    except Exception as e:
        reply = f"Error contacting OpenAI: {str(e)}"

    chat_history.append(("ai", reply))
    return jsonify({"reply": reply, "voice": None})

# Voice input route
@app.route("/voice", methods=["POST"])
def voice():
    if "voice" not in request.files:
        return jsonify({"reply": "No voice file received"}), 400

    voice_file = request.files["voice"]
    filename = f"{uuid.uuid4()}.webm"
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    voice_file.save(path)

    text = "[Voice input failed - please type message]"
    chat_history.append(("user", text))
    chat_history.append(("ai", "🤖 Voice support not available in this deployment yet"))

    return jsonify({"reply": "🤖 Voice support not available in this deployment yet", "voice": None})

# History routes
@app.route("/history")
def history():
    return jsonify(chat_history)

@app.route("/delete-history", methods=["POST"])
def delete_history():
    chat_history.clear()
    return jsonify({"status": "ok"})

# File uploads
@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"status": "No file"}), 400
    file = request.files["file"]
    filename = f"{uuid.uuid4()}_{file.filename}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({"status": "ok", "filename": filename})

# Google OAuth routes
@app.route("/login")
def login():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"]
    )
    return redirect(request_uri)

@app.route("/login/callback")
def callback():
    code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
    )
    client.parse_request_body_response(token_response.text)
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body).json()
    session["user"] = {"name": userinfo_response["name"], "email": userinfo_response["email"]}
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Run server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
