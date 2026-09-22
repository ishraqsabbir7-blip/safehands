import secrets
import time
import uuid
from backend.db import challenges
from backend.config import CHALLENGE_EXPIRY_SECONDS
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.exceptions import InvalidSignature

BASE = Path(__file__).resolve().parent


def create_challenge(action: str, amount: float) -> dict:
    """
    Creates a new pending challenge for a sensitive action.
    Returns the challenge dict that gets shown to the phone/dashboard.
    """
    challenge_id = str(uuid.uuid4())
    nonce = secrets.token_hex(16)
    now = time.time()
    expires_at = now + CHALLENGE_EXPIRY_SECONDS

    challenge = {
        "_id": challenge_id,
        "action": action,
        "amount": amount,
        "nonce": nonce,
        "created_at": now,
        "expires_at": expires_at,
        "status": "pending",
    }

    challenges.insert_one(challenge)
    return challenge


def build_message_to_sign(challenge: dict) -> bytes:
    """
    Builds the exact byte string that the phone must sign.
    Every field that matters is included, so changing any of them
    breaks the signature.
    """
    text = f"{challenge['_id']}|{challenge['action']}|{challenge['amount']}|{challenge['nonce']}"
    return text.encode()


def load_private_key():
    """Loads the device's private key (simulating the phone)."""
    with open(BASE / "device_private_key.pem", "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def load_public_key():
    """Loads the device's public key (what the server checks against)."""
    with open(BASE / "device_public_key.pem", "rb") as f:
        return serialization.load_pem_public_key(f.read())


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