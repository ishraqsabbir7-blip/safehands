import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import "./App.css";

const API_BASE = "http://127.0.0.1:5000/api";

const DEVICE_JWK = {
  kty: "EC",
  crv: "P-256",
  d: "nXG8pME174eOlfXnj8rSm914NzYxYwsZ98xmxKE8VPw",
  x: "mYhm_kRjbMoPcRqPgxYWk-BHKt0UTnLtOTkpPjiCU74",
  y: "PegLyLxNI0GylxD5ctsik2g_DJSRkIpaZunT6cFvXtc",
};

function buildMessageToSign(challenge) {
  const amountStr = Number(challenge.amount).toFixed(2);
  const text = `${challenge._id}|${challenge.action}|${amountStr}|${challenge.nonce}`;
  return new TextEncoder().encode(text);
}

async function signChallengeInBrowser(challenge) {
  const key = await window.crypto.subtle.importKey(
    "jwk",
    DEVICE_JWK,
    { name: "ECDSA", namedCurve: "P-256" },
    false,
    ["sign"]
  );
  const message = buildMessageToSign(challenge);
  const signatureRaw = await window.crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    key,
    message
  );
  return rawToDer(new Uint8Array(signatureRaw));
}

function rawToDer(raw) {
  const r = raw.slice(0, 32);
  const s = raw.slice(32, 64);
  function trim(bytes) {
    let i = 0;
    while (i < bytes.length - 1 && bytes[i] === 0) i++;
    bytes = bytes.slice(i);
    if (bytes[0] & 0x80) bytes = Uint8Array.from([0, ...bytes]);
    return bytes;
  }
  const rT = trim(r);
  const sT = trim(s);
  const rDer = [0x02, rT.length, ...rT];
  const sDer = [0x02, sT.length, ...sT];
  const body = [...rDer, ...sDer];
  return new Uint8Array([0x30, body.length, ...body]);
}

function bytesToBase64(bytes) {
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return window.btoa(binary);
}

function parseVoiceCommand(transcript) {
  const text = transcript.toLowerCase();
  let action = null;
  if (text.includes("bill") || text.includes("electricity")) {
    action = "pay_bill";
  } else if (text.includes("order") || text.includes("food")) {
    action = "order_food";
  } else if (text.includes("pay")) {
    action = "pay_bill";
  }
  const numberMatch = text.match(/(\d+)/);
  const amount = numberMatch ? parseFloat(numberMatch[1]) : null;
  return { action, amount };
}

const STEPS = [
  { icon: "🎙", title: "Speak", desc: "Alexa+ hears your request" },
  { icon: "🔏", title: "Sign", desc: "Your device signs the challenge" },
  { icon: "✅", title: "Verify", desc: "Server checks before acting" },
];

export default function App() {
  const [pending, setPending] = useState([]);
  const [log, setLog] = useState([]);
  const [logStatus, setLogStatus] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState("");
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [parsedPreview, setParsedPreview] = useState(null);
  const [justApproved, setJustApproved] = useState(null);
  const [tamperResult, setTamperResult] = useState(null);
  const recognitionRef = useRef(null);

  const fetchPending = useCallback(async () => {
    const res = await axios.get(`${API_BASE}/challenges/pending`);
    setPending(res.data);
  }, []);

  const fetchLog = useCallback(async () => {
    const res = await axios.get(`${API_BASE}/audit-log`);
    setLog(res.data);
    const verify = await axios.get(`${API_BASE}/audit-log/verify`);
    setLogStatus(verify.data);
  }, []);

  useEffect(() => {
    fetchPending();
    fetchLog();
    const interval = setInterval(() => {
      fetchPending();
      fetchLog();
    }, 4000);
    return () => clearInterval(interval);
  }, [fetchPending, fetchLog]);

  async function handleApprove(challenge) {
    setBusyId(challenge._id);
    setMessage("");
    try {
      const derSignature = await signChallengeInBrowser(challenge);
      const signatureB64 = bytesToBase64(derSignature);
      const res = await axios.post(
        `${API_BASE}/challenges/${challenge._id}/approve`,
        { signature: signatureB64 }
      );
      if (res.data.success) {
        setMessage(`Approved: ${challenge.action} for ${challenge.amount}`);
        setJustApproved(challenge._id);
        setTimeout(() => setJustApproved(null), 1200);
      } else {
        setMessage(`Rejected: ${res.data.reason}`);
      }
      fetchPending();
      fetchLog();
    } catch (err) {
      setMessage("Error: " + (err.response?.data?.reason || err.message));
    } finally {
      setBusyId(null);
    }
  }

  function startListening() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMessage("Voice recognition isn't supported in this browser. Try Chrome.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setListening(true);
      setTranscript("");
      setParsedPreview(null);
      setMessage("");
    };
    recognition.onresult = async (event) => {
      const said = event.results[0][0].transcript;
      setTranscript(said);
      const { action, amount } = parseVoiceCommand(said);
      setParsedPreview({ action, amount });
      if (!action || amount === null) {
        setMessage(`Couldn't understand: "${said}". Try "Pay my electricity bill, 2500."`);
        return;
      }
      try {
        await axios.post(`${API_BASE}/voice-command`, { action, amount });
        setMessage(`Request created from voice command.`);
        fetchPending();
      } catch (err) {
        setMessage("Error: " + (err.response?.data?.reason || err.message));
      }
    };
    recognition.onerror = (event) => {
      setMessage("Voice error: " + event.error);
      setListening(false);
    };
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    recognition.start();
  }

  async function handleSimulateTamper() {
    try {
      const res = await axios.post(`${API_BASE}/audit-log/simulate-tamper`);
      if (res.data.success) {
        setTamperResult(`Tampered with entry #${res.data.tampered_seq}. Re-checking chain...`);
        await fetchLog();
      } else {
        setTamperResult(res.data.reason);
      }
    } catch (err) {
      setTamperResult("Error: " + (err.response?.data?.reason || err.message));
    }
  }

  const approvedCount = log.filter((e) => e.data.event === "challenge_approved").length;

  return (
    <div className="app">
      <div className="stars" />
      <header className="header">
        <h1>SafeHands</h1>
        <p className="tagline">Cryptographic approval layer for Alexa+</p>
        <div className="status-row">
          <span><span className="status-dot"></span>MCP Server Online</span>
          <span><span className="status-dot"></span>Chain Verified</span>
        </div>
      </header>

      {message && <div className="banner">{message}</div>}

      <div className="layout">
        <aside className="sidebar">
          <div className="panel voice-panel">
            <h3>Voice Command</h3>
            <button
              className={`mic-btn ${listening ? "listening" : ""}`}
              onClick={startListening}
              disabled={listening}
            >
              {listening ? "Listening..." : "🎙 Talk to Alexa+"}
            </button>

            <div className={`transcript-box ${transcript ? "active" : ""}`}>
              {transcript ? (
                <>
                  <div className="transcript-heard">"{transcript}"</div>
                  {parsedPreview && (
                    <div className="parsed-chips">
                      <span className={`chip ${parsedPreview.action ? "chip-ok" : "chip-bad"}`}>
                        action: {parsedPreview.action || "?"}
                      </span>
                      <span className={`chip ${parsedPreview.amount !== null ? "chip-ok" : "chip-bad"}`}>
                        amount: {parsedPreview.amount ?? "?"}
                      </span>
                    </div>
                  )}
                </>
              ) : (
                <span className="transcript-placeholder">
                  Try: "Pay my electricity bill, 2500"
                </span>
              )}
            </div>
          </div>

          <div className="panel stats-panel">
            <h3>Live Stats</h3>
            <div className="stats-grid">
              <div className="stat">
                <div className="stat-num">{pending.length}</div>
                <div className="stat-label">Pending</div>
              </div>
              <div className="stat">
                <div className="stat-num">{approvedCount}</div>
                <div className="stat-label">Approved</div>
              </div>
              <div className="stat">
                <div className="stat-num">{log.length}</div>
                <div className="stat-label">Log Entries</div>
              </div>
            </div>
          </div>

          <div className="panel how-panel">
            <h3>How It Works</h3>
            {STEPS.map((s, i) => (
              <div className="how-step" key={i}>
                <span className="how-icon">{s.icon}</span>
                <div>
                  <div className="how-title">{s.title}</div>
                  <div className="how-desc">{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <main className="main-content">
          <section className="panel">
            <h2>Pending Approvals</h2>
            {pending.length === 0 ? (
              <div className="empty">
                <div className="empty-icon">🛰️</div>
                <p>No pending requests.</p>
                <p className="empty-sub">Use the voice button on the left.</p>
              </div>
            ) : (
              <div className="card-grid">
                {pending.map((c) => (
                  <div
                    className={`card ${justApproved === c._id ? "card-success" : ""}`}
                    key={c._id}
                  >
                    <div className="card-action">{c.action}</div>
                    <div className="card-amount">{c.amount}</div>
                    <div className="card-meta">
                      Expires: {new Date(c.expires_at * 1000).toLocaleTimeString()}
                    </div>
                    <button
                      className="approve-btn"
                      disabled={busyId === c._id}
                      onClick={() => handleApprove(c)}
                    >
                      {busyId === c._id ? "Signing..." : "Approve"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="panel log-panel">
            <h2>
              Audit Log{" "}
              {logStatus && (
                <span className={logStatus.valid ? "chip-valid" : "chip-broken"}>
                  {logStatus.valid ? "Chain Verified" : "Chain Broken"}
                </span>
              )}
              <button className="tamper-btn" onClick={handleSimulateTamper}>
                ⚠ Simulate Attack
              </button>
            </h2>
            {tamperResult && <p className="tamper-note">{tamperResult}</p>}
            {log.length === 0 ? (
              <div className="empty">
                <div className="empty-icon">📜</div>
                <p>No log entries yet.</p>
              </div>
            ) : (
              <div className="log-list">
                {log
                  .slice()
                  .reverse()
                  .map((entry) => (
                    <div className="log-entry" key={entry.seq}>
                      <span className="log-seq">#{entry.seq}</span>
                      <span className="log-event">{entry.data.event}</span>
                      <span className="log-detail">
                        {entry.data.action} — {entry.data.amount}
                      </span>
                      <span className="log-hash">{entry.hash.slice(0, 10)}...</span>
                    </div>
                  ))}
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}