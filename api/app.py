import os
import time
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, abort
import jwt

# Optional Redis usage
try:
    import redis
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False

# Load config from env or defaults
JWT_SECRET = os.environ.get("JWT_SECRET", "replace_this_with_strong_secret")
JWT_ALG = "HS256"
OTP_LENGTH = int(os.environ.get("OTP_LENGTH", 6))
OTP_VALIDITY_SECONDS = int(os.environ.get("OTP_VALIDITY_SECONDS", 120))   # OTP validity
SESSION_EXPIRY_SECONDS = int(os.environ.get("SESSION_EXPIRY_SECONDS", 120)) # doctor's session expiry
USE_REDIS = os.environ.get("USE_REDIS", "false").lower() == "true" and REDIS_AVAILABLE

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Flask(__name__)

# Storage backends
if USE_REDIS:
    r = redis.from_url(REDIS_URL, decode_responses=True)
else:
    # Simple in-memory dicts for demo (not persisted; single-process only)
    _otp_store = {}        # key => {h, salt, expires_at}
    _session_blacklist = {}  # jti => expires_at

# Utilities
def now_ts():
    return int(time.time())

def hash_otp(otp: str, salt: str) -> str:
    """HMAC-based OTP hashing (server-side)."""
    return hmac.new(salt.encode('utf-8'), otp.encode('utf-8'), hashlib.sha256).hexdigest()

def store_otp(doctor_id: str, otp: str, ttl: int):
    salt = secrets.token_hex(16)
    h = hash_otp(otp, salt)
    expires_at = now_ts() + ttl
    payload = {"h": h, "salt": salt, "expires_at": expires_at}
    key = f"otp:{doctor_id}"
    if USE_REDIS:
        r.hset(key, mapping=payload)
        r.expireat(key, expires_at)
    else:
        _otp_store[key] = payload

def get_otp_record(doctor_id: str):
    key = f"otp:{doctor_id}"
    if USE_REDIS:
        if not r.exists(key):
            return None
        data = r.hgetall(key)
        data["expires_at"] = int(data["expires_at"])
        return data
    else:
        return _otp_store.get(key)

def remove_otp(doctor_id: str):
    key = f"otp:{doctor_id}"
    if USE_REDIS:
        r.delete(key)
    else:
        _otp_store.pop(key, None)

def create_session_token(doctor_id: str, expiry_seconds: int):
    """Create JWT with short expiry. Includes jti for blacklist support."""
    exp = datetime.utcnow() + timedelta(seconds=expiry_seconds)
    jti = secrets.token_hex(16)
    payload = {"sub": doctor_id, "exp": exp, "iat": datetime.utcnow(), "jti": jti}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    return token, jti, int(exp.timestamp())

def blacklist_session(jti: str, expires_at_ts: int):
    if USE_REDIS:
        r.setex(f"black:{jti}", expires_at_ts - now_ts(), "1")
    else:
        _session_blacklist[jti] = expires_at_ts

def is_blacklisted(jti: str):
    if USE_REDIS:
        return r.exists(f"black:{jti}")
    else:
        exp = _session_blacklist.get(jti)
        if not exp:
            return False
        if now_ts() >= exp:
            _session_blacklist.pop(jti, None)
            return False
        return True

# Demo patient DB (replace with your real DB)
PATIENT_DB = {
    "ramesh": {
        "name": "Ramesh Kumar",
        "dob": "1990-05-12",
        "last_visit": "2025-11-21",
        "notes": "Hypertension — controlled"
    }
}

# OTP generator utility
def generate_otp(length=6):
    digits = ''.join(str(secrets.randbelow(10)) for _ in range(length))
    return digits

# Demo OTP sender (replace with Twilio / SMTP in production)
def send_otp_demo(doctor_id: str, otp: str):
    app.logger.info(f"[DEMO OTP] OTP for {doctor_id} is: {otp}")

# ---------------- API Endpoints ----------------

@app.route("/api/request_otp", methods=["POST"])
def api_request_otp():
    data = request.get_json(force=True, silent=True) or {}
    doctor_id = (data.get("doctor_id") or "").strip()
    if not doctor_id:
        return jsonify({"error": "doctor_id required"}), 400

    otp = generate_otp(OTP_LENGTH)
    store_otp(doctor_id, otp, OTP_VALIDITY_SECONDS)
    send_otp_demo(doctor_id, otp)
    return jsonify({
        "ok": True,
        "message": "OTP generated and sent (demo)",
        "otp_validity_seconds": OTP_VALIDITY_SECONDS
    }), 200

@app.route("/api/verify_otp", methods=["POST"])
def api_verify_otp():
    data = request.get_json(force=True, silent=True) or {}
    doctor_id = (data.get("doctor_id") or "").strip()
    otp_in = (data.get("otp") or "").strip()
    if not doctor_id or not otp_in:
        return jsonify({"error": "doctor_id and otp required"}), 400

    rec = get_otp_record(doctor_id)
    if not rec:
        return jsonify({"error": "no valid otp found for this identifier or it expired"}), 400

    if now_ts() > int(rec["expires_at"]):
        remove_otp(doctor_id)
        return jsonify({"error": "otp expired"}), 400

    expected_hash = rec["h"]
    salt = rec["salt"]
    if not hmac.compare_digest(expected_hash, hash_otp(otp_in, salt)):
        return jsonify({"error": "invalid otp"}), 401

    remove_otp(doctor_id)
    token, jti, expires_at_ts = create_session_token(doctor_id, SESSION_EXPIRY_SECONDS)
    return jsonify({
        "ok": True,
        "token": token,
        "expires_at": expires_at_ts,
        "session_expires_in_seconds": SESSION_EXPIRY_SECONDS
    }), 200

def decode_token_and_validate(auth_header: str):
    if not auth_header:
        abort(401, "missing authorization header")
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        abort(401, "invalid authorization header")
    token = parts[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        abort(401, "token expired")
    except Exception:
        abort(401, "invalid token")

    jti = payload.get("jti")
    if not jti:
        abort(401, "invalid token payload")
    if is_blacklisted(jti):
        abort(401, "session invalidated")
    return payload

@app.route("/api/patient/<patient_id>", methods=["GET"])
def api_get_patient(patient_id):
    payload = decode_token_and_validate(request.headers.get("Authorization"))
    rec = PATIENT_DB.get(patient_id)
    if not rec:
        return jsonify({"error": "patient not found"}), 404
    return jsonify({"ok": True, "patient": rec}), 200

@app.route("/api/logout", methods=["POST"])
def api_logout():
    payload = decode_token_and_validate(request.headers.get("Authorization"))
    jti = payload.get("jti")
    exp_ts = payload.get("exp")
    if jti:
        blacklist_session(jti, int(exp_ts))
    return jsonify({"ok": True, "message": "logged out"}), 200

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "time": now_ts()}), 200

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
