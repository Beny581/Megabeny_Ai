from flask import Flask, request, jsonify, render_template, redirect, session, send_from_directory
import os
import uuid
import requests
from oauthlib.oauth2 import WebApplicationClient
from langdetect import detect

# ===== OPENAI (UPDATED SDK) =====
from openai import OpenAI

# ===== CONFIG FROM ENV =====
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = os.environ.get(
    "GOOGLE_DISCOVERY_URL",
    "https://accounts.google.com/.well-known/openid-configuration"
)
SECRET_KEY = os.environ.get("SECRET_KEY", "megabenysecret")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")

# ===== FLASK SETUP =====
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===== OPENAI CLIENT =====
client_ai = OpenAI(api_key=OPENAI_API_KEY)

# ===== GOOGLE OAUTH CLIENT =====
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# ===== IN-MEMORY CHAT HISTORY =====
chat_history = []

# ================= ROUTES =================

@app.route("/")
def home():
    user = session.get("user")
    return render_template("index.html", user=user)

# ---------- CHAT ----------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    msg = data.get("message") if data else None

    if not msg:
        return jsonify({"reply": "Tafadhali andika ujumbe"}), 400

    chat_history.append(("user", msg))

    # Detect language safely
    try:
        lang = detect(msg) if len(msg.strip()) > 3 else "sw"
    except:
        lang = "sw"

    # System prompt
    if lang.startswith("en"):
        system_prompt = (
            "You are Megabeny AI, a skilled assistant. "
            "Always greet new users with: 'Welcome to Megabeny AI for excellent service'. "
            "Provide clear, fast, and practical help."
        )
    else:
        system_prompt = (
            "Wewe ni Megabeny AI, msaidizi mahiri. "
            "Kila mteja mpya umkaribishe kwa kusema: "
            "'Karibu Megabeny AI kwa huduma bora'. "
            "Toa msaada wa haraka, wa kueleweka, na wa vitendo."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": msg}
    ]

    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = "Samahani, kuna hitilafu ya mtandao. Jaribu tena."

    chat_history.append(("ai", reply))
    return jsonify({"reply": reply, "voice": None})

# ---------- VOICE (SAFE PLACEHOLDER) ----------
@app.route("/voice", methods=["POST"])
def voice():
    if "voice" not in request.files:
        return jsonify({"reply": "Hakuna sauti iliyopokelewa"}), 400

    voice_file = request.files["voice"]
    filename = f"{uuid.uuid4()}.webm"
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    voice_file.save(path)

    # Voice processing placeholder (stable)
    reply = "🤖 Huduma ya sauti bado inaboreshwa. Tafadhali andika ujumbe."

    chat_history.append(("user", "[voice message]"))
    chat_history.append(("ai", reply))

    return jsonify({"reply": reply, "voice": None})

# ---------- HISTORY ----------
@app.route("/history")
def history():
    return jsonify(chat_history)

@app.route("/delete-history", methods=["POST"])
def delete_history():
    chat_history.clear()
    return jsonify({"status": "ok"})

# ---------- FILE UPLOAD ----------
@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"status": "No file"}), 400

    file = request.files["file"]
    filename = f"{uuid.uuid4()}_{file.filename}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    return jsonify({"status": "ok", "filename": filename})

# ---------- GOOGLE LOGIN ----------
@app.route("/login")
def login():
    google_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_cfg["authorization_endpoint"]

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"]
    )
    return redirect(request_uri)

@app.route("/login/callback")
def callback():
    code = request.args.get("code")
    google_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_cfg["token_endpoint"]

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

    userinfo_endpoint = google_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo = requests.get(uri, headers=headers, data=body).json()

    session["user"] = {
        "name": userinfo.get("name"),
        "email": userinfo.get("email")
    }

    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------- SERVE UPLOADS ----------
@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ===== RUN SERVER =====
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
