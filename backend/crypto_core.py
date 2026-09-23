import hashlib
import json
import secrets
import time
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from backend.config import CHALLENGE_EXPIRY_SECONDS
from backend.db import audit_log, challenges

BASE = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Challenge creation
# ---------------------------------------------------------------------------

def create_challenge(action: str, amount: float) -> dict:
    """
    Creates a new pending challenge for a sensitive action.
    Returns the challenge dict that gets shown to the phone/dashboard.
    """
    challenge_id = str(uuid.uuid4())
    nonce = secrets.token_hex(16)  # random, unpredictable, one-time value
    now = time.time()
    expires_at = now + CHALLENGE_EXPIRY_SECONDS

    challenge = {
        "_id": challenge_id,
        "action": action,
        "amount": amount,
        "nonce": nonce,
        "created_at": now,
        "expires_at": expires_at,
        "status": "pending",   # pending -> approved / expired / rejected
    }

    challenges.insert_one(challenge)
    return challenge


def build_message_to_sign(challenge: dict) -> bytes:
    """
    Builds the exact byte string that the phone must sign.
    Every field that matters is included, so changing any of them
    breaks the signature.

    Amount is formatted to a fixed 2 decimal places, because Python
    and JavaScript format whole-number floats differently by default
    (2500.0 vs 2500), which would otherwise silently break cross-language
    signature verification. Both crypto_core.py and App.jsx must format
    amounts identically.
    """
    amount_str = f"{float(challenge['amount']):.2f}"
    text = f"{challenge['_id']}|{challenge['action']}|{amount_str}|{challenge['nonce']}"
    return text.encode()


# ---------------------------------------------------------------------------
# Key loading (simulated device key pair)
# ---------------------------------------------------------------------------

def load_private_key():
    """Loads the device's private key (simulating the phone)."""
    with open(BASE / "device_private_key.pem", "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def load_public_key():
    """Loads the device's public key (what the server checks against)."""
    with open(BASE / "device_public_key.pem", "rb") as f:
        return serialization.load_pem_public_key(f.read())


# ---------------------------------------------------------------------------
# Signing and verification
# ---------------------------------------------------------------------------

def sign_challenge(challenge: dict) -> bytes:
    """
    Simulates the phone signing the challenge.
    In a real app this runs on the device; here we do it locally for the demo.
    """
    private_key = load_private_key()
    message = build_message_to_sign(challenge)
    return private_key.sign(message, ec.ECDSA(hashes.SHA256()))


def verify_signature(challenge: dict, signature: bytes) -> bool:
    """
    Server-side check: does this signature match this exact challenge?
    """
    public_key = load_public_key()
    message = build_message_to_sign(challenge)
    try:
        public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


# ---------------------------------------------------------------------------
# Hash-chained audit log
# ---------------------------------------------------------------------------

def _compute_entry_hash(data: dict, prev_hash: str) -> str:
    """Same idea as the try_chain.py experiment."""
    text = json.dumps(data, sort_keys=True) + prev_hash
    return hashlib.sha256(text.encode()).hexdigest()


def add_log_entry(data: dict) -> dict:
    """
    Appends a new entry to the audit log, linked to the previous entry's hash.
    """
    last_entry = audit_log.find_one(sort=[("seq", -1)])
    prev_hash = last_entry["hash"] if last_entry else "0" * 64
    seq = (last_entry["seq"] + 1) if last_entry else 0

    entry_hash = _compute_entry_hash(data, prev_hash)

    entry = {
        "seq": seq,
        "data": data,
        "prev_hash": prev_hash,
        "hash": entry_hash,
        "timestamp": time.time(),
    }

    audit_log.insert_one(entry)
    return entry


def verify_log() -> dict:
    """
    Walks the entire chain and checks it hasn't been tampered with.
    """
    entries = list(audit_log.find(sort=[("seq", 1)]))
    prev_hash = "0" * 64

    for entry in entries:
        if entry["prev_hash"] != prev_hash:
            return {"valid": False, "broken_at": entry["seq"], "reason": "prev_hash mismatch"}
        expected_hash = _compute_entry_hash(entry["data"], entry["prev_hash"])
        if expected_hash != entry["hash"]:
            return {"valid": False, "broken_at": entry["seq"], "reason": "data was edited"}
        prev_hash = entry["hash"]

    return {"valid": True, "entries_checked": len(entries)}


# ---------------------------------------------------------------------------
# Main approval flow (ties everything together)
# ---------------------------------------------------------------------------

def approve_challenge(challenge_id: str, signature: bytes) -> dict:
    """
    The main server-side check. Called when a signed approval comes in.
    Returns a result dict explaining what happened.
    """
    challenge = challenges.find_one({"_id": challenge_id})

    if challenge is None:
        return {"success": False, "reason": "Challenge not found"}

    if challenge["status"] != "pending":
        return {"success": False, "reason": f"Challenge already {challenge['status']}"}

    if time.time() > challenge["expires_at"]:
        challenges.update_one({"_id": challenge_id}, {"$set": {"status": "expired"}})
        return {"success": False, "reason": "Challenge expired"}

    if not verify_signature(challenge, signature):
        return {"success": False, "reason": "Invalid signature"}

    # Atomic: only succeeds if it's STILL pending at this exact moment.
    # This is what actually stops two simultaneous replay attempts.
    result = challenges.find_one_and_update(
        {"_id": challenge_id, "status": "pending"},
        {"$set": {"status": "approved", "approved_at": time.time()}}
    )

    if result is None:
        return {"success": False, "reason": "Challenge was already used (race condition caught)"}

    add_log_entry({
        "event": "challenge_approved",
        "challenge_id": challenge_id,
        "action": challenge["action"],
        "amount": challenge["amount"],
    })

    return {"success": True, "reason": "Approved", "challenge": challenge}