import secrets
import time
import uuid
from backend.db import challenges
from backend.config import CHALLENGE_EXPIRY_SECONDS


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
    """
    text = f"{challenge['_id']}|{challenge['action']}|{challenge['amount']}|{challenge['nonce']}"
    return text.encode()