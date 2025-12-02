import React, { useEffect, useRef, useState } from "react";
import { sendMessage, getSession, requestDoctorReportApi } from "./api";
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
  const [messages, setMessages] = useState([]); 
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState("patient"); 
  const [toolCalls, setToolCalls] = useState([]);
  const bottomRef = useRef();

  useEffect(() => {
    let sid = localStorage.getItem("mcp_session_id");
    if (!sid) {
      sid = uid();
      localStorage.setItem("mcp_session_id", sid);
    }
    setSessionId(sid);

    (async () => {
      try {
        const data = await getSession(sid);
        if (data && data.history) {
          const mapped = data.history.map(h => ({ role: h.role, content: h.content, time: h.time }));
          setMessages(mapped);
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

  // Doctor: request summary & notify
  async function requestDoctorReport() {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await requestDoctorReportApi("Dr. Ahuja", null, true);
      if (res && res.summary_text) {
        const assistantMsg = {
          role: "assistant",
          content: res.summary_text + "\n\nNotification sent: " + (res.notification_sent ? "Yes" : "No"),
          time: Math.floor(Date.now() / 1000)
        };
        setMessages(m => [...m, assistantMsg]);
      } else {
        const assistantMsg = { role: "assistant", content: "No summary returned.", time: Math.floor(Date.now()/1000) };
        setMessages(m => [...m, assistantMsg]);
      }
    } catch (err) {
      const msg = { role: "assistant", content: "Failed to fetch report.", time: Math.floor(Date.now()/1000) };
      setMessages(m => [...m, msg]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <header className="topbar">
        <h1>Agentic Healthcare Assistant</h1>
        <div className="controls">
          <label className="role-toggle">
            <select value={role} onChange={e=>setRole(e.target.value)}>
              <option value="patient">Patient</option>
              <option value="doctor">Doctor</option>
            </select>
          </label>

          {role === "doctor" && (
            <button disabled={loading} onClick={requestDoctorReport}>Send Summary & Notify</button>
          )}
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

        {role === "doctor" && (
          <aside className="sidebar">
            <div className="card">
              <h3>Doctor Dashboard</h3>
              <p>Use "Send Summary & Notify" to push today's summary to your notification channel.</p>
            </div>
          </aside>
        )}
      </main>

      <footer className="footer">
        <small>Agentic Healthcare Assistant</small>
      </footer>
    </div>
  );
}
