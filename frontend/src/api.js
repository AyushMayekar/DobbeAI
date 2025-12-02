import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

export async function sendMessage(session_id, message) {
    const payload = { session_id, message };
    const res = await axios.post(`${API_BASE}/api/ai`, payload, { timeout: 30000 });
    return res.data;
}

export async function getSession(session_id) {
    const res = await axios.get(`${API_BASE}/api/session/${session_id}`);
    return res.data;
}

export async function requestDoctorReportApi(doctor_name = "Dr. Ahuja", ref_date = null, send_notification = true) {
    const payload = { doctor_name, ref_date, send_notification };
    const res = await axios.post(`${API_BASE}/doctor/report`, payload, { timeout: 20000 });
    return res.data;
}