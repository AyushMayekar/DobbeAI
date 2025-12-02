from app.mcp import tools
from app import ai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title = "MCP BACKEND")

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

# AI API endpoints
class AIRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

@app.post("/api/ai")
def api_ai(payload: AIRequest):
    if not payload.message or payload.message.strip() == "":
        raise HTTPException(status_code=400, detail="message required")
    result = ai.process_user_message(payload.session_id, payload.message)
    return result

@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    return ai.dump_session(session_id)

class ReportRequest(BaseModel):
    doctor_name: str
    ref_date: Optional[str] = None
    send_notification: Optional[bool] = True

@app.post("/doctor/report")
def doctor_report(payload: ReportRequest):
    res = tools.get_doctor_summary_report(payload.doctor_name, payload.ref_date, payload.send_notification)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res