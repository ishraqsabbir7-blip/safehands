"""
One-time script: exports the device private key as a JWK (JSON Web Key)
so it can be imported into the browser via WebCrypto's importKey().
This lets the DASHBOARD do the real signing, not the server.
"""
import json
from cryptography.hazmat.primitives.asymmetric import ec
from backend.crypto_core import load_private_key

private_key = load_private_key()
numbers = private_key.private_numbers()

def to_base64url(n: int, length: int = 32) -> str:
    import base64
    b = n.to_bytes(length, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

public_numbers = numbers.public_numbers

jwk = {
    "kty": "EC",
    "crv": "P-256",
    "d": to_base64url(numbers.private_value),
    "x": to_base64url(public_numbers.x),
    "y": to_base64url(public_numbers.y),
}

print(json.dumps(jwk, indent=2))