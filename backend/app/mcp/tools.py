from datetime import datetime, date, time, timedelta
from typing import List, Dict
from app.db import SessionLocal
from app.models import Doctor, Appointment
from sqlalchemy import func
from .resources import (
    daterange,
    parse_time_of_day_filter,
    send_calendar_event_stub,
    send_email_stub,
    time_to_iso,
)
import os, requests

SLOT_MINUTES = 60  # use 60-minute appointment slots for simplicity

def _normalize_doc_name(name: str) -> str:
    if not name:
        return ""
    name = name.strip().lower()
    if not name.startswith("dr"):
        return f"dr. {name}"
    return name.replace("  ", " ").replace("dr ", "dr. ").strip()


def _get_doctor_by_name(db, doctor_name: str):
    if not doctor_name:
        return None

    target = _normalize_doc_name(doctor_name)

    # exact match only
    doc = db.query(Doctor).filter(func.lower(Doctor.name) == target).first()

    return doc

def _existing_slots_for_date(db, doctor_id: int, target_date: date) -> List[time]:
    rows = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.date == target_date
    ).all()
    return [r.start_time for r in rows]

def get_doctor_availability(doctor_name: str, start_date_str: str, end_date_str: str = None, time_of_day: str = None) -> Dict:
    """
    Returns available slots between start_date and end_date (inclusive).
    start_date_str, end_date_str expected in YYYY-MM-DD format.
    """
    db = SessionLocal()
    try:
        doc = _get_doctor_by_name(db, doctor_name)
        if not doc:
            return {"ok": False, "error": f"Doctor '{doctor_name}' not found"}

        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = start_date if not end_date_str else datetime.fromisoformat(end_date_str).date()
        start_hour, end_hour = parse_time_of_day_filter(time_of_day)
        available = []

        for single_date in daterange(start_date, end_date):
            existing = _existing_slots_for_date(db, doc.id, single_date)
            # generate hourly slots
            hour = start_hour
            while hour < end_hour:
                slot_start = time(hour, 0)
                slot_end_hour = hour + (SLOT_MINUTES // 60)
                slot_end = time(slot_end_hour, 0)
                if slot_start not in existing:
                    # append ISO strings
                    available.append({
                        "date": single_date.isoformat(),
                        "start_time": slot_start.isoformat(),
                        "end_time": slot_end.isoformat(),
                        "start_iso": time_to_iso(single_date, slot_start),
                        "end_iso": time_to_iso(single_date, slot_end)
                    })
                hour += (SLOT_MINUTES // 60)
        return {"ok": True, "doctor": doc.name, "available_slots": available}
    finally:
        db.close()

def create_appointment(doctor_name: str, patient_name: str, patient_email: str, start_iso: str, end_iso: str, reason: str = None) -> Dict:
    """
    Create appointment in DB. Attempt to create calendar event and send email.
    start_iso/end_iso are ISO 8601 datetime strings.
    """
    db = SessionLocal()
    try:
        doc = _get_doctor_by_name(db, doctor_name)
        if not doc:
            return {"ok": False, "error": f"Doctor '{doctor_name}' not found"}

        start_dt = datetime.fromisoformat(start_iso)
        end_dt = datetime.fromisoformat(end_iso)
        # Check conflict
        conflict = db.query(Appointment).filter(
            Appointment.doctor_id == doc.id,
            Appointment.date == start_dt.date(),
            Appointment.start_time == start_dt.time()
        ).first()
        if conflict:
            return {"ok": False, "error": "Slot already booked"}

        appt = Appointment(
            doctor_id=doc.id,
            patient_name=patient_name,
            date=start_dt.date(),
            start_time=start_dt.time(),
            end_time=end_dt.time(),
            reason=reason or ""
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)

        cal_result = send_calendar_event_stub(doc.name, patient_name, start_dt.isoformat(), end_dt.isoformat())
        email_result = send_email_stub(patient_email, f"Appointment with {doc.name}", f"Your appointment on {start_dt.isoformat()}")

        return {
            "ok": True,
            "appointment_id": appt.id,
            "calendar": cal_result,
            "email": email_result
        }
    finally:
        db.close()

def get_doctor_stats(doctor_name: str, ref_date_str: str = None) -> dict:
    db = SessionLocal()
    try:
        doc = _get_doctor_by_name(db, doctor_name)
        if not doc:
            return {"ok": False, "error": f"Doctor '{doctor_name}' not found"}

        if ref_date_str:
            ref_date = datetime.fromisoformat(ref_date_str).date()
        else:
            ref_date = date.today()

        yesterday = ref_date - timedelta(days=1)
        tomorrow = ref_date + timedelta(days=1)

        def count_on(target_date):
            return db.query(func.count(Appointment.id)).filter(
                Appointment.doctor_id == doc.id,
                Appointment.date == target_date
            ).scalar() or 0

        count_yesterday = count_on(yesterday)
        count_today = count_on(ref_date)
        count_tomorrow = count_on(tomorrow)

        rows = db.query(Appointment.reason).filter(
            Appointment.doctor_id == doc.id,
            Appointment.date == ref_date
        ).all()

        # aggregate reasons with normalization
        breakdown = {}
        for (reason,) in rows:  
            key = _normalize_reason(reason)
            breakdown[key] = breakdown.get(key, 0) + 1

        # sort top reasons
        top_reasons = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)

        return {
            "ok": True,
            "doctor": doc.name,
            "ref_date": ref_date.isoformat(),
            "patients_yesterday": count_yesterday,
            "patients_today": count_today,
            "patients_tomorrow": count_tomorrow,
            "reasons_breakdown": breakdown,
            "top_reasons": [{"reason": r, "count": c} for r, c in top_reasons]
        }
    finally:
        db.close()

def _normalize_reason(reason: str) -> str:
    if not reason:
        return "other"
    r = reason.lower().strip()
    if any(k in r for k in ("fever", "temperature", "hot")):
        return "fever"
    if any(k in r for k in ("check", "checkup", "routine", "follow-up", "follow up", "consult")):
        return "checkup"
    if any(k in r for k in ("cough", "cold", "flu", "sore", "throat")):
        return "respiratory"
    if any(k in r for k in ("pain", "ache", "injury", "back", "headache", "head ache")):
        return "pain"
    if any(k in r for k in ("prescription", "med", "refill")):
        return "prescription"
    token = r.split()[0][:20]
    return token or "other"

# Slack helper (simple webhook)
def _send_slack_message(text: str) -> dict:
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        return {"ok": False, "error": "no_slack_webhook"}
    payload = {"text": text}
    try:
        resp = requests.post(webhook, json=payload, timeout=5)
        return {"ok": resp.status_code in (200, 201, 204), "status_code": resp.status_code, "text": resp.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_doctor_summary_report(doctor_name: str, ref_date_str: str = None, send_notification: bool = True) -> dict:
    """
    Returns a human-friendly summary and optionally sends Slack notification.
    """
    stats = get_doctor_stats(doctor_name, ref_date_str)
    if not stats.get("ok"):
        return {"ok": False, "error": stats.get("error")}

    lines = []
    lines.append(f"Summary report for {stats['doctor']} — {stats['ref_date']}")
    lines.append(f"- Patients yesterday: {stats['patients_yesterday']}")
    lines.append(f"- Patients today: {stats['patients_today']}")
    lines.append(f"- Patients tomorrow: {stats['patients_tomorrow']}")
    lines.append("- Reason breakdown:")
    if stats.get("top_reasons"):
        for tr in stats["top_reasons"]:
            lines.append(f"  • {tr['reason'].title()}: {tr['count']}")
    else:
        lines.append("  • No categorized reasons for this date.")

    summary_text = "\n".join(lines)

    notification_result = None
    if send_notification:
        notification_result = _send_slack_message(summary_text)

    return {
        "ok": True,
        "doctor": stats["doctor"],
        "ref_date": stats["ref_date"],
        "summary_text": summary_text,
        "notification_sent": bool(notification_result and notification_result.get("ok")),
        "notification_result": notification_result,
        "raw_stats": stats,
    }
