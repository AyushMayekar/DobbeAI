from app.mcp import tools
from app.db import SessionLocal
from app.models import Doctor
from app import ai
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid

app = FastAPI(title = "MCP BACKEND")

DOCTOR_EMAIL_MAP = {
    "mehta@clinic.com": "Dr. Mehta",
    "sharma@clinic.com": "Dr. Sharma",
    "roy@clinic.com": "Dr. Roy",
    "joy@clinic.com": "Dr. Joy",
    "joshi@clinic.com": "Dr. Joshi",
    "ahuja@clinic.com": "Dr. Ahuja",
}

TOKENS = {}

# CORS middleware - allows frontend to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

@app.get("/health")
def health():
    return {"ok": True}

# Simple login endpoint
class LoginRequest(BaseModel):
    email: str
    role: str  # "patient" or "doctor"

class LoginResponse(BaseModel):
    token: str
    role: str
    doctor_name: Optional[str] = None

@app.post("/auth/login", response_model=LoginResponse)
def auth_login(payload: LoginRequest):
    email = payload.email.strip().lower()
    role = payload.role.strip().lower()
    if role not in ("patient", "doctor"):
        raise HTTPException(status_code=400, detail="role must be 'patient' or 'doctor'")

    doctor_name = None
    if role == "doctor":
        if email not in DOCTOR_EMAIL_MAP:
            raise HTTPException(status_code=403, detail="Unknown doctor email")
        doctor_name = DOCTOR_EMAIL_MAP[email]

    token = str(uuid.uuid4())
    TOKENS[token] = {"email": email, "role": role, "doctor_name": doctor_name}
    return {"token": token, "role": role, "doctor_name": doctor_name}

def get_token_info(x_auth: Optional[str] = Header(None), x_role: Optional[str] = Header(None)):
    if not x_auth:
        raise HTTPException(status_code=401, detail="X-AUTH header required")
    info = TOKENS.get(x_auth)
    if not info:
        raise HTTPException(status_code=401, detail="Invalid token")
    if x_role and info.get("role") != x_role:
        raise HTTPException(status_code=403, detail="Role mismatch")
    return info

# AI API endpoints
class AIRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

@app.post("/api/ai")
def api_ai(payload: AIRequest, token_info: dict = Depends(get_token_info)):
    if not payload.message or payload.message.strip() == "":
        raise HTTPException(status_code=400, detail="message required")
    result = ai.process_user_message(payload.session_id, payload.message, token_info=token_info)
    return result

@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    return ai.dump_session(session_id)

class ReportRequest(BaseModel):
    doctor_name: Optional[str] = None
    ref_date: Optional[str] = None
    send_notification: Optional[bool] = True

@app.post("/doctor/report")
def doctor_report(payload: ReportRequest, token_info: dict = Depends(get_token_info), x_role: Optional[str] = Header(None)):
    if token_info.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="Forbidden: requires doctor role")
    if payload.doctor_name:
        if token_info.get("doctor_name") and token_info.get("doctor_name") != payload.doctor_name:
            raise HTTPException(status_code=403, detail="Forbidden: cannot request other doctor's report")
    doctor_name_to_use = payload.doctor_name or token_info.get("doctor_name")
    if not doctor_name_to_use:
        raise HTTPException(status_code=400, detail="doctor_name required for report")
    res = tools.get_doctor_summary_report(doctor_name_to_use, payload.ref_date, payload.send_notification)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.get("/doctors")
def list_doctors():
    db = SessionLocal()
    try:
        rows = db.query(Doctor).all()
        return [{"id": d.id, "name": d.name} for d in rows]
    finally:
        db.close()