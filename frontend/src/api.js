import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

function authHeaders() {
    const token = localStorage.getItem("mcp_token");
    const role = localStorage.getItem("mcp_role") || "";
    const headers = {};
    if (token) headers["X-AUTH"] = token;
    if (role) headers["X-ROLE"] = role;
    return headers;
}

export async function sendMessage(session_id, message) {
    const payload = { session_id, message };
    const res = await axios.post(`${API_BASE}/api/ai`, payload, { headers: authHeaders(), timeout: 30000 });
    return res.data;
}

export async function getSession(session_id) {
    const res = await axios.get(`${API_BASE}/api/session/${session_id}`, { headers: authHeaders() });
    return res.data;
}

export async function requestDoctorReportApi(doctor_name = null, ref_date = null, send_notification = true) {
    const payload = { doctor_name, ref_date, send_notification };
    const res = await axios.post(`${API_BASE}/doctor/report`, payload, { headers: authHeaders(), timeout: 20000 });
    return res.data;
}


export async function loginApi(email, role) {
    const res = await axios.post(`${API_BASE}/auth/login`, { email, role }, { timeout: 10000 });
    return res.data;
}