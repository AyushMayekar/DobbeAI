import os
import uuid
import time
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# OpenAI client: only initialize if API key present
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_OPENAI = bool(OPENAI_API_KEY)

openai_client = None
if USE_OPENAI:
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print("OpenAI client init failed:", e)
        openai_client = None
        USE_OPENAI = False

# MCP tools
from app.mcp import tools as mcp_tools

# Sessions (in-memory)
sessions: Dict[str, List[Dict[str, Any]]] = {}
SESSION_MAX_LEN = 20


def _now_ts():
    return int(time.time())


def create_session() -> str:
    sid = str(uuid.uuid4())
    sessions[sid] = []
    return sid


def append_session(session_id: str, role: str, content: str):
    if session_id not in sessions:
        sessions[session_id] = []
    sessions[session_id].append({"role": role, "content": content, "time": _now_ts()})
    if len(sessions[session_id]) > SESSION_MAX_LEN:
        sessions[session_id] = sessions[session_id][-SESSION_MAX_LEN:]


def get_session_history(session_id: str) -> List[Dict[str, Any]]:
    return sessions.get(session_id, [])


def build_tools_schema():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_doctor_availability",
                "description": "Return available slots for a doctor.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doctor_name": {"type": "string"},
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "time_of_day": {"type": "string"},
                    },
                    "required": ["doctor_name", "start_date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_appointment",
                "description": "Book an appointment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doctor_name": {"type": "string"},
                        "patient_name": {"type": "string"},
                        "patient_email": {"type": "string"},
                        "start_iso": {"type": "string"},
                        "end_iso": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": [
                        "doctor_name",
                        "patient_name",
                        "patient_email",
                        "start_iso",
                        "end_iso",
                    ],
                },
            },
        },
        {
    "type": "function",
    "function": {
    "name": "get_doctor_summary_report",
    "description": "Return a summary report of patient counts and reasons, and optionally notify the doctor through Slack.",
    "parameters": {
        "type": "object",
        "properties": {
        "doctor_name": { "type": "string", "description": "Doctor full name, e.g. 'Dr. Ahuja'." },
        "ref_date": { "type": "string", "description": "Reference date in YYYY-MM-DD format (optional). If omitted, defaults to today." },
        "send_notification": { "type": "boolean", "description": "If true, send the summary to the doctor's Slack webhook (if configured)." }
        },
        "required": ["doctor_name"]
    }
    }
}
    ]


# Call the MCP tool functions
def call_tool_by_name(name: str, args: dict):
    try:
        if name == "get_doctor_availability":
            return mcp_tools.get_doctor_availability(
                doctor_name=args.get("doctor_name"),
                start_date_str=args.get("start_date"),
                end_date_str=args.get("end_date"),
                time_of_day=args.get("time_of_day"),
            )
        if name == "create_appointment":
            return mcp_tools.create_appointment(
                doctor_name=args.get("doctor_name"),
                patient_name=args.get("patient_name"),
                patient_email=args.get("patient_email"),
                start_iso=args.get("start_iso"),
                end_iso=args.get("end_iso"),
                reason=args.get("reason"),
            )
        if name == "get_doctor_summary_report":
            return mcp_tools.get_doctor_summary_report(
                doctor_name=args.get("doctor_name"),
                ref_date_str=args.get("ref_date"),
                send_notification=args.get("send_notification", True)
            )
        return {"ok": False, "error": f"Unknown tool '{name}'"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def summarize_tool_outputs(tool_outputs: List[Dict[str, Any]]) -> str:
    """
    Create readable text from tool outputs if the model fails to produce a good summary.
    """
    lines = []
    for entry in tool_outputs:
        tool = entry.get("tool")
        res = entry.get("result", {})
        if tool == "get_doctor_availability":
            slots = res.get("available_slots", [])
            if not slots:
                lines.append("No available slots found.")
            else:
                lines.append("Available slots:")
                for s in slots[:6]:
                    lines.append(f" • {s['start_iso']} — {s['end_iso']}")
        elif tool == "create_appointment":
            if res.get("ok"):
                appt_id = res.get("appointment_id")
                cal_note = res.get("calendar", {}).get("htmlLink") or res.get("calendar", {}).get("note", "")
                lines.append(f"Appointment created (id: {appt_id}). {cal_note}")
            else:
                lines.append(f"Failed to create appointment: {res.get('error')}")
        elif tool == "get_doctor_summary_report":
            if res.get("ok"):
                summary_text = res.get("summary_text")
                if summary_text and isinstance(summary_text, str) and summary_text.strip():
                    lines.append(summary_text)
                    notified = res.get("notification_sent", False)
                    lines.append("")
                    lines.append(f"Notification sent: {'Yes' if notified else 'No'}")
                else:
                    # Build summary from raw_stats
                    raw = res.get("raw_stats", {})
                    doc = raw.get("doctor", "Doctor")
                    ref = raw.get("ref_date", "")
                    y = raw.get("patients_yesterday", 0)
                    t = raw.get("patients_today", 0)
                    tm = raw.get("patients_tomorrow", 0)

                    # top_reasons preferred
                    top = raw.get("top_reasons") or []
                    if top:
                        parts = [f"• {r['reason'].title()}: {r['count']}" for r in top[:10]]
                    else:
                        rb = raw.get("reasons_breakdown", {})
                        parts = [f"• {k.title()}: {v}" for k, v in sorted(rb.items(), key=lambda x: -x[1])][:10]

                    lines.append(f"Summary report for {doc} — {ref}")
                    lines.append("")
                    lines.append(f"- Patients yesterday: {y}")
                    lines.append("")
                    lines.append(f"- Patients today: {t}")
                    lines.append("")
                    lines.append(f"- Patients tomorrow: {tm}")
                    lines.append("")
                    lines.append("- Reason breakdown:")
                    lines.append("")
                    if parts:
                        lines.extend(parts)
                    else:
                        lines.append("• No categorized reasons available.")
                    notified = res.get("notification_sent", False)
                    lines.append("")
                    lines.append(f"Notification sent: {'Yes' if notified else 'No'}")
            else:
                lines.append(f"Stats error: {res.get('error')}")
        else:
            lines.append(json.dumps(res))
    return "\n".join(lines) if lines else "No results."


def mock_agent_reply(session_id: str, message: str) -> Dict[str, Any]:
    msg = message.lower()
    tool_calls = []
    reply = "I didn't understand. Try: 'check Dr. Ahuja availability', 'book 2025-12-02T09:00 for John', or 'how many patients yesterday'."

    # doctor extraction
    m = re.search(r"dr\.?\s+([a-zA-Z]+)", message, re.IGNORECASE)
    doctor_name = "Dr. Ahuja" if not m else f"Dr. {m.group(1).title()}"

    today = datetime.utcnow().date()
    if "tomorrow" in msg:
        start_date = (today + timedelta(days=1)).isoformat()
    elif "yesterday" in msg:
        start_date = (today - timedelta(days=1)).isoformat()
    else:
        start_date = today.isoformat()

    # availability intent
    if "availability" in msg or "available" in msg or "slots" in msg:
        res = call_tool_by_name("get_doctor_availability", {"doctor_name": doctor_name, "start_date": start_date})
        tool_calls.append({"tool": "get_doctor_availability", "args": {"doctor_name": doctor_name, "start_date": start_date}, "result": res})
        if res.get("ok"):
            slots = res.get("available_slots", [])
            if not slots:
                reply = f"No slots available for {doctor_name} on {start_date}."
            else:
                first = slots[:5]
                lines = [f"- {s['start_iso']} to {s['end_iso']}" for s in first]
                reply = f"Available slots for {doctor_name} on {start_date}:\n" + "\n".join(lines)
        else:
            reply = f"Error: {res.get('error')}"

    # stats intent
    elif "how many" in msg or "patients" in msg or "visited" in msg:
        ref_date = None
        if "yesterday" in msg:
            ref_date = (today - timedelta(days=1)).isoformat()
        elif "tomorrow" in msg:
            ref_date = (today + timedelta(days=1)).isoformat()
        elif "today" in msg:
            ref_date = today.isoformat()

            res = call_tool_by_name(
                "get_doctor_summary_report",
                {
                    "doctor_name": doctor_name,
                    "ref_date": ref_date,
                    "send_notification": True
                }
            )
            tool_calls.append({
                "tool": "get_doctor_summary_report",
                "args": {"doctor_name": doctor_name, "ref_date": ref_date, "send_notification": True},
                "result": res
            })

            if res.get("ok"):
                summary = res.get("summary_text")
                if summary and isinstance(summary, str) and summary.strip():
                    notified = res.get("notification_sent", False)
                    reply = f"{summary}\n\nNotification sent: {'Yes' if notified else 'No'}"
                else:
                    raw = res.get("raw_stats", {})
                    doc = raw.get("doctor", doctor_name)
                    ref = raw.get("ref_date", ref_date or "")
                    y = raw.get("patients_yesterday", 0)
                    t = raw.get("patients_today", 0)
                    tm = raw.get("patients_tomorrow", 0)

                    top = raw.get("top_reasons") or []
                    if top:
                        parts = [f"• {r['reason'].title()}: {r['count']}" for r in top[:10]]
                    else:
                        rb = raw.get("reasons_breakdown", {})
                        parts = [f"• {k.title()}: {v}" for k, v in sorted(rb.items(), key=lambda x: -x[1])][:10]

                    lines = [
                        f"Summary report for {doc} — {ref}",
                        "",
                        f"- Patients yesterday: {y}",
                        "",
                        f"- Patients today: {t}",
                        "",
                        f"- Patients tomorrow: {tm}",
                        "",
                        "- Reason breakdown:",
                        ""
                    ]
                    lines.extend(parts if parts else ["• No categorized reasons available."])
                    notified = res.get("notification_sent", False)
                    lines.append("")
                    lines.append(f"Notification sent: {'Yes' if notified else 'No'}")

                    reply = "\n".join(lines)
            else:
                reply = f"Error: {res.get('error')}"

        else:
            reply = f"Error: {res.get('error')}"

    # booking intent
    elif "book" in msg or "schedule" in msg:
        dt_match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})", message)
        name_match = re.search(r"dr\.?\s+([a-zA-Z]+)", message, re.IGNORECASE)
        patient_match = re.search(r"for\s+([A-Za-z ]+)", message, re.IGNORECASE)
        doctor_name = "Dr. Ahuja" if not name_match else f"Dr. {name_match.group(1).title()}"
        patient_name = "Patient" if not patient_match else patient_match.group(1).strip().title()

        if dt_match:
            start_iso = dt_match.group(1) + ":00"
            sd = datetime.fromisoformat(start_iso)
            end_iso = (sd + timedelta(hours=1)).isoformat()
            patient_email = "patient@example.com"
            res = call_tool_by_name("create_appointment", {
                "doctor_name": doctor_name,
                "patient_name": patient_name,
                "patient_email": patient_email,
                "start_iso": start_iso,
                "end_iso": end_iso,
                "reason": "Booked via mock agent"
            })
            tool_calls.append({"tool": "create_appointment", "args": {"doctor_name": doctor_name, "start_iso": start_iso}, "result": res})
            if res.get("ok"):
                reply = f"Booked {doctor_name} at {start_iso} for {patient_name}. Appointment id: {res.get('appointment_id')}"
            else:
                reply = f"Booking failed: {res.get('error')}"
        else:
            # show availability suggestions (for today)
            res = call_tool_by_name("get_doctor_availability", {"doctor_name": doctor_name, "start_date": today.isoformat()})
            tool_calls.append({"tool": "get_doctor_availability", "args": {"doctor_name": doctor_name, "start_date": today.isoformat()}, "result": res})
            if res.get("ok"):
                slots = res.get("available_slots", [])[:5]
                if slots:
                    options = "\n".join([s["start_iso"] for s in slots])
                    reply = f"I don't see a datetime in your request. Here are the next available slots for {doctor_name}:\n{options}\nPlease say 'Book <ISO-datetime>' to confirm."
                else:
                    reply = "No available slots found to book."
            else:
                reply = f"Error: {res.get('error')}"

    return {"reply": reply, "tool_calls": tool_calls}


# OpenAI agent flow 
def openai_agent_reply(session_id: str, user_message: str) -> Dict[str, Any]:
    if not openai_client:
        return {"reply": "OpenAI client not initialized; falling back to mock.", "tool_calls": []}

    history = get_session_history(session_id)

    messages = [{"role": "system", "content":
                    "You are an assistant for a medical appointment system. "
                    "You may call tools to check availability, create appointments, or fetch stats. "
                    "When you call a tool, use the tools API (tool_calls). After tool output is provided, produce a short, human-friendly summary for the user. "
                    "Use ISO datetimes for start_iso/end_iso."}]

    # Append only user/assistant history
    for item in history:
        if item["role"] in ("user", "assistant"):
            messages.append({"role": item["role"], "content": item["content"]})

    messages.append({"role": "user", "content": user_message})

    tools = build_tools_schema()

    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )
    except Exception as e:
        return {"reply": f"OpenAI error: {e} (falling back to mock)", "tool_calls": []}

    choice = resp.choices[0]
    message = choice.message

    # If model requested tool_calls
    if hasattr(message, "tool_calls") and getattr(message, "tool_calls"):
        tool_outputs = []
        # For each tool call the model asked for, execute it
        for call in message.tool_calls:
            tool_name = call.function.name
            raw_args = call.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
            except:
                args = {}
            result = call_tool_by_name(tool_name, args)
            tool_outputs.append({"tool": tool_name, "args": args, "result": result})

            # Append the tool output back to the LLM conversation in the required format
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result)
            })

        try:
            final_resp = openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages,
                temperature=0.25,
            )
            final_message = final_resp.choices[0].message
            final_text = final_message.content if getattr(final_message, "content", None) else None
        except Exception as e:
            final_text = None

        if not final_text or final_text.strip() == "" or final_text.strip().lower().startswith("tool result"):
            final_text = summarize_tool_outputs(tool_outputs)

        # Save assistant reply and return
        append_session(session_id, "assistant", final_text)
        return {"reply": final_text, "tool_calls": tool_outputs}

    # No tool call, return model's direct content
    assistant_text = message.content if getattr(message, "content", None) else ""
    append_session(session_id, "assistant", assistant_text)
    return {"reply": assistant_text, "tool_calls": []}


def process_user_message(session_id: Optional[str], message: str) -> Dict[str, Any]:
    if not session_id:
        session_id = create_session()
    append_session(session_id, "user", message)

    if USE_OPENAI and openai_client:
        out = openai_agent_reply(session_id, message)
        mode = "openai"
    else:
        out = mock_agent_reply(session_id, message)
        mode = "mock"

    append_session(session_id, "assistant", out.get("reply", ""))
    return {"ok": True, "session_id": session_id, "reply": out.get("reply"), "tool_calls": out.get("tool_calls", []), "mode": mode}

# Debug helper
def dump_session(session_id: str) -> Dict[str, Any]:
    return {"session_id": session_id, "history": get_session_history(session_id)}
