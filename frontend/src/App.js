import React, { useEffect, useRef, useState } from "react";
import { sendMessage, getSession, requestDoctorReportApi, loginApi } from "./api";
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
      <div className="msg-content">{m.content.split("\n").map((t, i) => (<p key={i}>{t}</p>))}</div>
    </div>
  );
}

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState(localStorage.getItem("mcp_role") || "patient");
  const [toolCalls, setToolCalls] = useState([]);
  const bottomRef = useRef();
  const [token, setToken] = useState(localStorage.getItem("mcp_token") || null);
  const [email, setEmail] = useState("");
  const [loginRole, setLoginRole] = useState("patient"); // default
  const [doctorName, setDoctorName] = useState(localStorage.getItem("mcp_doctor_name") || null);


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
      const errorMsg = { role: "assistant", content: "Error: failed to reach backend.", time: Math.floor(Date.now() / 1000) };
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
      const res = await requestDoctorReportApi(null, null, true);
      if (res && res.summary_text) {
        const assistantMsg = {
          role: "assistant",
          content: res.summary_text + "\n\nNotification sent: " + (res.notification_sent ? "Yes" : "No"),
          time: Math.floor(Date.now() / 1000)
        };
        setMessages(m => [...m, assistantMsg]);
      } else {
        const assistantMsg = { role: "assistant", content: "No summary returned.", time: Math.floor(Date.now() / 1000) };
        setMessages(m => [...m, assistantMsg]);
      }
    } catch (err) {
      const msg = { role: "assistant", content: "Failed to fetch report.", time: Math.floor(Date.now() / 1000) };
      setMessages(m => [...m, msg]);
    } finally {
      setLoading(false);
    }
  }  

  function logout() {
    localStorage.removeItem("mcp_token");
    localStorage.removeItem("mcp_role");
    localStorage.removeItem("mcp_doctor_name");
    setToken(null);
    setDoctorName(null);
    setMessages([]);
    setRole("patient");
  }  

  if (!token) {
    return (
      <div className="container" style={{padding:20}}>
        <h2>Login (demo)</h2>
        <p>Use a predefined doctor email for doctor role (e.g. mehta@clinic.com)</p>
        <div style={{maxWidth:420}}>
          <label>Email</label>
          <input value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@domain.com" />
          <label>Role</label>
          <select value={loginRole} onChange={e=>setLoginRole(e.target.value)}>
            <option value="patient">Patient</option>
            <option value="doctor">Doctor</option>
          </select>
          <div style={{marginTop:10}}>
            <button onClick={async ()=>{
              setLoading(true);
              try {
                const data = await loginApi(email, loginRole);
                localStorage.setItem("mcp_token", data.token);
                localStorage.setItem("mcp_role", data.role);
                setRole(data.role);
                if (data.doctor_name) {
                  localStorage.setItem("mcp_doctor_name", data.doctor_name);
                  setDoctorName(data.doctor_name);
                }
                setToken(data.token);
              } catch (err) {
                alert("Login failed: " + (err.response?.data?.detail || err.message));
              } finally {
                setLoading(false);
              }
            }} disabled={loading || !email}>Continue</button>
          </div>
        </div>
      </div>
    );
  }  

  return (
    <div className="container">
      <header className="topbar">
        <h1>Agentic Healthcare Assistant</h1>
        <div className="controls">
          <label className="role-toggle">
            <select value={role} onChange={e => setRole(e.target.value)} disabled={!!token}>
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
