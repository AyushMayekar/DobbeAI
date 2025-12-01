# File: backend/app/mcp/tools.py
"""
MCP tools: DB-driven functions the LLM can call.
Keep outputs simple JSON-serializable.
"""
from datetime import datetime, date, time, timedelta
from typing import List, Dict
from app.db import SessionLocal
from app.models import Doctor, Appointment
from .resources import (
    daterange,
    parse_time_of_day_filter,
    send_calendar_event_stub,
    send_email_stub,
    time_to_iso,
)

SLOT_MINUTES = 60  # use 60-minute appointment slots for simplicity

def _get_doctor_by_name(db, doctor_name: str):
    return db.query(Doctor).filter(Doctor.name.ilike(f"%{doctor_name}%")).first()

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

def get_doctor_stats(doctor_name: str, ref_date_str: str = None) -> Dict:
    """
    Return counts: yesterday, today, tomorrow, and 'fever' keyword count.
    ref_date_str defaults to today (YYYY-MM-DD).
    """
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
            return db.query(Appointment).filter(
                Appointment.doctor_id == doc.id,
                Appointment.date == target_date
            ).count()

        count_yesterday = count_on(yesterday)
        count_today = count_on(ref_date)
        count_tomorrow = count_on(tomorrow)

        # fever cases: simple keyword match in reason
        fever_cases = db.query(Appointment).filter(
            Appointment.doctor_id == doc.id,
            Appointment.reason.ilike("%fever%")
        ).count()

        return {
            "ok": True,
            "doctor": doc.name,
            "patients_yesterday": count_yesterday,
            "patients_today": count_today,
            "patients_tomorrow": count_tomorrow,
            "fever_cases": fever_cases
        }
    finally:
        db.close()
