from datetime import datetime, timedelta, time
from typing import Dict
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import json
import base64

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  
GOOGLE_DIR = os.path.join(BASE_DIR, "google")
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", os.path.join(GOOGLE_DIR, "credentials.json"))
TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", os.path.join(GOOGLE_DIR, "token.json"))

# Google scopes we need for Calendar events and Gmail send
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_google_credentials(scopes=SCOPES) -> Credentials or None:
    if not os.path.exists(CREDENTIALS_PATH):
        return None

    creds = None
    # Load existing token if present
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                creds = None
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, scopes)
                creds = flow.run_local_server(port=0)
                # Save token for next runs
                with open(TOKEN_PATH, "w") as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                return None
    return creds

def send_calendar_event_google(doctor_name: str, patient_name: str, start_iso: str, end_iso: str) -> Dict:
    creds = get_google_credentials()
    if not creds:
        # Fallback simulated result
        return {"ok": True, "source": "simulated_calendar", "note": "missing_credentials_or_token"}

    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        event = {
            "summary": f"Appointment: {patient_name} with {doctor_name}",
            "description": f"Appointment booked via MCP system. Patient: {patient_name}",
            "start": {"dateTime": start_iso, "timeZone": "UTC"},
            "end": {"dateTime": end_iso, "timeZone": "UTC"},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return {"ok": True, "source": "google_calendar", "event_id": created.get("id"), "htmlLink": created.get("htmlLink")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_email_gmail_api(to_email: str, subject: str, body_text: str, from_name: str = None) -> Dict:

    creds = get_google_credentials()
    if not creds:
        return {"ok": True, "source": "simulated_email", "note": "missing_credentials_or_token"}

    try:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        message = MIMEText(body_text, "plain")
        if from_name:
            message["From"] = from_name
        message["To"] = to_email
        message["Subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"ok": True, "source": "gmail_api", "message_id": send_result.get("id")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_calendar_event_stub(doctor_name: str, patient_name: str, start_iso: str, end_iso: str):
    res = send_calendar_event_google(doctor_name, patient_name, start_iso, end_iso)
    if res is None:
        return {"ok": True, "source": "simulated", "note": "calendar_skipped_no_creds"}
    return res

def send_email_stub(to_email: str, subject: str, body: str):
    res = send_email_gmail_api(to_email, subject, body)
    if res is None:
        return {"ok": True, "source": "simulated", "note": "email_skipped_no_creds"}
    return res   

def daterange(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)

def time_to_iso(dt_date, dt_time):
    return datetime.combine(dt_date, dt_time).isoformat()

def parse_time_of_day_filter(time_of_day: str):
    """
    Accept 'morning', 'afternoon', 'evening', or None.
    Return (start_hour, end_hour)
    """
    if not time_of_day:
        return (9, 17)  
    t = time_of_day.lower()
    if t == "morning":
        return (9, 12)
    if t == "afternoon":
        return (12, 16)
    if t == "evening":
        return (16, 19)
    return (9, 17)

def ensure_google_folder():
    if not os.path.exists(GOOGLE_DIR):
        os.makedirs(GOOGLE_DIR, exist_ok=True)