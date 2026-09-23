from mcp.server.mcpserver import MCPServer
from backend.crypto_core import create_challenge, sign_challenge, approve_challenge
from backend.db import challenges

mcp = MCPServer("safehands")


@mcp.tool()
def request_action(action: str, amount: float) -> dict:
    """
    Called by Alexa+ when the user asks for a sensitive action
    (e.g. 'pay my electricity bill, 2500 taka').
    Creates a challenge that must be approved on the owner's device
    before the action runs.
    """
    challenge = create_challenge(action, amount)
    return {
        "status": "pending_approval",
        "challenge_id": challenge["_id"],
        "message": f"Please approve this on your SafeHands dashboard: {action} for {amount}",
    }


@mcp.tool()
def check_status(challenge_id: str) -> dict:
    """
    Called by Alexa+ to check whether the user has approved the action yet.
    """
    challenge = challenges.find_one({"_id": challenge_id})
    if challenge is None:
        return {"status": "not_found"}
    return {"status": challenge["status"]}


@mcp.tool()
def approve_pending(challenge_id: str) -> dict:
    """
    Simulates the phone approving a pending challenge.
    In the real product, signing happens ON the phone (WebCrypto),
    and only the signature is sent here. For this demo, we sign
    locally using the device's private key file.
    """
    challenge = challenges.find_one({"_id": challenge_id})
    if challenge is None:
        return {"success": False, "reason": "Challenge not found"}

    signature = sign_challenge(challenge)
    result = approve_challenge(challenge_id, signature)
    return result


if __name__ == "__main__":
    mcp.run(transport="streamable-http")