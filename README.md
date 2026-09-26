# safehands
Cryptographic approval layer for Alexa+: sensitive voice actions run only after ECDSA-signed approval from the owner's device.
# SafeHands

Cryptographic approval layer for Alexa+. No sensitive action goes through until the owner's device signs it with ECDSA. Alexa can hear you, but it can't act until your phone says yes.

Built for the Build, Ship, Shape: Amazon Developer Hackathon — Alexa+ track, Open Source mini challenge.

---

## Why this exists

Alexa+ is starting to do things for you, not just answer questions: paying bills, placing orders, sharing information. That's useful, but a voice alone doesn't prove much. A guest in the room, a kid messing around, even a recording, could trigger something they shouldn't be able to. SafeHands puts a real cryptographic check in front of anything sensitive, so a voice can start a request but can't finish it alone.

## How it actually works

1. You ask Alexa+ (or our voice simulation) to do something sensitive — "Pay my electricity bill, 2500."
2. The MCP server doesn't just do it. It creates a challenge: a random nonce, a 60-second expiry, and the action details.
3. Your device (the dashboard in the browser, standing in for a phone) signs that exact challenge with ECDSA (P-256), using the browser's own WebCrypto API. The private key never leaves the device.
4. The server checks the signature, checks the nonce hasn't already been used (this is done atomically, so two requests hitting at the same instant can't both sneak through), and checks it hasn't expired.
5. Once it's valid, the action goes through, and the event gets appended to a SHA-256 hash-chained audit log. Each entry stores the hash of the one before it, so if someone edits an old entry later, the chain breaks from that point forward and it's obvious.
6. There's a "Simulate Attack" button on the dashboard that deliberately corrupts a log entry, so you can watch the chain catch it live instead of just taking our word for it.

## What's in the repo
exa+ (voice) ──▶ MCP Server (Streamable HTTP, spec 2025-11-25+) ──┐
├──▶ crypto_core.py ──▶ MongoDB Atlas
Browser (voice sim + dashboard) ──▶ Flask REST API ──────────────────┘

- **`backend/crypto_core.py`** — this is the actual security logic: creating challenges, signing/verifying with ECDSA, atomic replay protection, the hash chain. It doesn't know or care whether MCP or Flask called it, which is deliberate.
- **`backend/mcp_server.py`** — exposes three tools (`request_action`, `check_status`, `approve_pending`) that Alexa+ would call, built on the MCP Python SDK over Streamable HTTP.
- **`backend/api.py`** — a Flask API that the React dashboard talks to. Same underlying logic, different front door.
- **`backend/db.py`** — MongoDB Atlas connection.
- **`dashboard/`** — the React (Vite) dashboard. Voice input through the Web Speech API, live pending-approval cards, real in-browser ECDSA signing, and a live audit log with the tamper demo.

## Running it yourself

You'll need Python 3.10+, Node 18+, a free MongoDB Atlas cluster (M0 tier is fine), and Chrome (for the voice input to work).

**1. Clone it and set up the backend**

```bash
git clone https://github.com/ishraqsabbir7-blip/safehands.git
cd safehands
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r backend/requirements.txt
```

**2. Set your environment variables**

Create `backend/.env`:
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
DB_NAME=safehands

**3. Generate a device key pair**

```bash
python -m backend.generate_keys
```

This creates `backend/device_private_key.pem` and `backend/device_public_key.pem`. For this demo, we're using one key pair to stand in for "the phone's" secure storage — more on that below.

**4. Start all three pieces (three separate terminals, all from the project root)**

```bash
# Terminal 1 — the MCP server, this is what Alexa+ would talk to
python -m backend.mcp_server

# Terminal 2 — the Flask API, this is what the dashboard talks to
python -m backend.api

# Terminal 3 — the dashboard itself
cd dashboard
npm install
npm run dev
```

Open whatever URL Vite gives you (usually `http://localhost:5173`).

**5. Try it out**

Click the mic button and say something like "Pay my electricity bill, 2500." A pending approval card shows up — click Approve, and you'll see the browser actually sign it with ECDSA before the server accepts it. Then open the Audit Log panel and hit Simulate Attack to watch the chain catch a tampered entry in real time.

## Testing the MCP server on its own

There's a small script that acts as a real MCP client, connects over Streamable HTTP, lists the tools, and runs the whole request → approve → check-status loop:

```bash
python backend/test_mcp_client.py
```

## What we simplified, and why

We're upfront about the gaps here rather than pretending they don't exist:

- **One shared key pair, not per-device keys.** A real product would register a public key per user/device rather than hardcoding one pair for the whole demo.
- **Voice input is simulated in the browser instead of wired to a real Alexa+ device.** Registering a real MCP add-on with Alexa+ needs OAuth account linking, a public HTTPS endpoint, and — per Amazon's own docs — the MCP Toolkit is currently US-only. That's more infrastructure than we could reasonably set up without an actual Alexa device to test against, in the time we had. The MCP server itself is the real thing though — genuine Streamable HTTP, spec 2025-11-25+, tested against an actual MCP client — so a live Alexa+ connection could be dropped in later without changing anything server-side.
- **Payment execution is mocked.** The point here is the trust layer around the action, not building a real payment gateway.

## Product feedback and friction log

Real issues we hit while building this — an MCP SDK version that broke our imports mid-project, a signature verification bug caused by JS and Python formatting numbers differently, a MongoDB serialization bug that failed silently — are all documented in [`FRICTION_LOG.md`](./FRICTION_LOG.md), along with how we found and fixed each one.

## License

MIT — see [`LICENSE`](./LICENSE).