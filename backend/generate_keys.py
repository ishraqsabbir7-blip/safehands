from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from pathlib import Path

BASE = Path(__file__).resolve().parent

private_key = ec.generate_private_key(ec.SECP256R1())
public_key = private_key.public_key()

# Save private key (simulates the phone's secure storage)
with open(BASE / "device_private_key.pem", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

# Save public key (simulates what the server knows about the phone)
with open(BASE / "device_public_key.pem", "wb") as f:
    f.write(public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ))

print("Keys generated:")
print(" -", BASE / "device_private_key.pem")
print(" -", BASE / "device_public_key.pem")