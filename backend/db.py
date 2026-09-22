import os
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent / ".env")

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "safehands")

if not MONGO_URI:
    raise ValueError("MONGO_URI not found. Check your .env file.")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections we'll use
challenges = db["challenges"]
audit_log = db["audit_log"]


def check_connection():
    """Quick test: ping the database."""
    try:
        client.admin.command("ping")
        return True
    except Exception as e:
        print("Connection failed:", e)
        return False