import React, { useEffect, useRef, useState } from "react";
import { sendMessage, getSession } from "./api";
import "./index.css";

function uid() {
  return "sess-" + Math.random().toString(36).slice(2, 10);
}

function Message({ m }) {
  const cls = m.role === "user" ? "msg user" : "msg assistant";
  return (
    <div className={cls}>
      <div className="msg-meta">
        <span className="role">{m.role}</span>
        <span className="time">{new Date(m.time * 1000).toLocaleTimeString()}</span>
      </div>
      <div className="msg-content">{m.content.split("\n").map((t,i)=>(<p key={i}>{t}</p>))}</div>
    </div>
  );
}

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]); // {role,content,time}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState("patient"); // patient | doctor
  const [toolCalls, setToolCalls] = useState([]);
  const bottomRef = useRef();

  useEffect(() => {
    // load or create session id
    let sid = localStorage.getItem("mcp_session_id");
    if (!sid) {
      sid = uid();
      localStorage.setItem("mcp_session_id", sid);
    }
    setSessionId(sid);
    // optional: fetch session history from backend (debug)
    (async () => {
      try {
        const data = await getSession(sid);
        if (data && data.history) {
          // convert history to our messages format
          setMessages((prev) => {
            const mapped = data.history.map(h => ({ role: h.role, content: h.content, time: h.time }));
            return mapped;
          });
        }
      } catch (e) {
        // ignore
      }
    })();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(text) {
    if (!text || !text.trim()) return;
    const userMsg = { role: "user", content: text.trim(), time: Math.floor(Date.now() / 1000) };
    setMessages(m => [...m, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const res = await sendMessage(sessionId, text.trim());
      const assistantText = res.reply || "(no reply)";
      const assistantMsg = { role: "assistant", content: assistantText, time: Math.floor(Date.now() / 1000) };
      setMessages(m => [...m, assistantMsg]);
      if (res.tool_calls) setToolCalls(res.tool_calls);
      if (res.session_id && res.session_id !== sessionId) {
        setSessionId(res.session_id);
        localStorage.setItem("mcp_session_id", res.session_id);
      }
    } catch (err) {
      console.error(err);
      const errorMsg = { role: "assistant", content: "Error: failed to reach backend.", time: Math.floor(Date.now()/1000) };
      setMessages(m => [...m, errorMsg]);
    } finally {
      setLoading(false);
    }
  }

  function onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  }

  function quickDoctorStats() {
    // simple natural-language prompt for doctor stats
    const q = "How many patients did I have yesterday?";
    handleSend(q);
  }

  return (
    <div className="container">
      <header className="topbar">
        <h1>Agentic MCP — App</h1>
        <div className="controls">
          <label className="role-toggle">
            <select value={role} onChange={e=>setRole(e.target.value)}>
              <option value="patient">Patient</option>
              <option value="doctor">Doctor</option>
            </select>
          </label>
          <button className="dash-btn" onClick={quickDoctorStats}>Doctor: Get Yesterday's Stats</button>
        </div>
      </header>

      <main className="main">
        <section className="chat">
          <div className="messages">
            {messages.map((m, idx) => <Message key={idx} m={m} />)}
            <div ref={bottomRef} />
          </div>

          <div className="composer">
            <textarea
              placeholder="Type a message (e.g. 'I want to book Dr. Ahuja tomorrow morning')"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKey}
            />
            <div className="composer-controls">
              <button className="send" onClick={() => handleSend(input)} disabled={loading}>
                {loading ? "Sending..." : "Send"}
              </button>
            </div>
          </div>
        </section>

        <aside className="sidebar">
          <div className="card">
            <h3>Session</h3>
            <p><strong>session_id:</strong></p>
            <code className="sid">{sessionId}</code>
            <p><strong>mode:</strong> {loading ? "waiting..." : "idle"}</p>
          </div>

          <div className="card">
            <h3>Tool Calls (debug)</h3>
            {toolCalls && toolCalls.length ? (
              toolCalls.map((t, i) => (
                <details key={i} className="tool">
                  <summary>{t.tool} — {t.result && t.result.ok ? "ok":"err"}</summary>
                  <pre>{JSON.stringify(t, null, 2)}</pre>
                </details>
              ))
            ) : <p>No tool calls yet.</p>}
          </div>

          <div className="card">
            <h3>Shortcuts</h3>
            <button onClick={()=>handleSend("Check Dr. Ahuja availability today morning")}>Check Dr. Ahuja (today)</button>
            <button onClick={()=>handleSend("I want to book an appointment with Dr. Ahuja tomorrow morning")}>Book (start flow)</button>
          </div>
        </aside>
      </main>

      <footer className="footer">
        <small>Agentic MCP demo — React client</small>
      </footer>
    </div>
  );
}
