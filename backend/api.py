import base64

from flask import Flask, jsonify, request
from flask_cors import CORS

from backend.crypto_core import approve_challenge, verify_log
from backend.db import audit_log, challenges

app = Flask(__name__)
CORS(app)  # allows the React dashboard (different port) to call this API


@app.route("/api/challenges/pending", methods=["GET"])
def get_pending_challenges():
    """List all challenges waiting for approval and not yet expired."""
    import time
    pending = list(challenges.find({
        "status": "pending",
        "expires_at": {"$gt": time.time()}
    }))
    return jsonify(pending)


@app.route("/api/challenges/<challenge_id>/approve", methods=["POST"])
def approve(challenge_id):
    """
    The dashboard sends a base64-encoded signature here after the
    browser signs the challenge with WebCrypto.
    """
    data = request.get_json()
    if not data or "signature" not in data:
        return jsonify({"success": False, "reason": "Missing signature"}), 400

    signature = base64.b64decode(data["signature"])
    result = approve_challenge(challenge_id, signature)
    return jsonify(result)


@app.route("/api/audit-log", methods=["GET"])
def get_audit_log():
    """Return the full audit log, oldest first."""
    entries = list(audit_log.find(sort=[("seq", 1)]))
    return jsonify(entries)


@app.route("/api/audit-log/verify", methods=["GET"])
def verify_audit_log():
    """Check whether the hash chain is intact."""
    return jsonify(verify_log())


@app.route("/api/health", methods=["GET"])
def health():
    """Simple check that the API is alive."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(port=5000, debug=True)