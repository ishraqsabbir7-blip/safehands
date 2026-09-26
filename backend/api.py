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
    entries = list(audit_log.find({}, {"_id": 0}, sort=[("seq", 1)]))
    return jsonify(entries)


@app.route("/api/audit-log/verify", methods=["GET"])
def verify_audit_log():
    """Check whether the hash chain is intact."""
    return jsonify(verify_log())


@app.route("/api/health", methods=["GET"])
def health():
    """Simple check that the API is alive."""
    return jsonify({"status": "ok"})


@app.route("/api/voice-command", methods=["POST"])
def voice_command():
    """
    Simulates what Alexa+ would do: takes a parsed voice command
    and creates a challenge. Uses the same crypto_core function
    as the real MCP request_action tool.
    """
    from backend.crypto_core import create_challenge

    data = request.get_json()
    action = data.get("action")
    amount = data.get("amount")

    if not action or amount is None:
        return jsonify({"success": False, "reason": "Could not understand the command"}), 400

    challenge = create_challenge(action, float(amount))
    return jsonify({
        "success": True,
        "challenge_id": challenge["_id"],
        "message": f"Created a pending request: {action} for {amount}",
    })
@app.route("/api/audit-log/simulate-tamper", methods=["POST"])
def simulate_tamper():
    """
    DEMO-ONLY: deliberately corrupts one log entry to prove the
    hash chain detects tampering. Never expose this in a real product.
    """
    first_entry = audit_log.find_one(sort=[("seq", 1)])
    if not first_entry:
        return jsonify({"success": False, "reason": "No log entries to tamper with"}), 400

    # Corrupt the amount in the earliest entry, without recomputing its hash
    tampered_data = dict(first_entry["data"])
    tampered_data["amount"] = 999999

    audit_log.update_one(
        {"seq": first_entry["seq"]},
        {"$set": {"data": tampered_data}}
    )

    return jsonify({"success": True, "tampered_seq": first_entry["seq"]})


if __name__ == "__main__":
    app.run(port=5000, debug=True)