# backend/app/main.py  (snippet to ensure /doctors exists)
from app.db import SessionLocal
from app.models import Doctor
from app.mcp import tools
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title = "MCP BACKEND")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/mcp/schema")
def mcp_schema():
    """
    Minimal discovery schema: LLM can fetch this to see available tools.
    """
    return {
        "tools": [
            {
                "name": "get_doctor_availability",
                "description": "Get available appointment slots for a doctor between dates",
                "args": {"doctor_name": "string", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD (optional)", "time_of_day": "morning|afternoon|evening (optional)"}
            },
            {
                "name": "create_appointment",
                "description": "Create an appointment and notify patient",
                "args": {"doctor_name": "string", "patient_name": "string", "patient_email": "string", "start_iso": "ISO datetime", "end_iso": "ISO datetime", "reason": "string (optional)"}
            },
            {
                "name": "get_doctor_stats",
                "description": "Get simple appointment stats for doctor",
                "args": {"doctor_name": "string", "ref_date": "YYYY-MM-DD (optional)"}
            }
        ]
    }

class ToolCall(BaseModel):
    tool: str
    args: dict

@app.post("/mcp/tool")
def call_tool(payload: ToolCall):
    t = payload.tool
    args = payload.args or {}
    try:
        if t == "get_doctor_availability":
            return tools.get_doctor_availability(
                doctor_name=args.get("doctor_name"),
                start_date_str=args.get("start_date"),
                end_date_str=args.get("end_date"),
                time_of_day=args.get("time_of_day"),
            )
        if t == "create_appointment":
            return tools.create_appointment(
                doctor_name=args.get("doctor_name"),
                patient_name=args.get("patient_name"),
                patient_email=args.get("patient_email"),
                start_iso=args.get("start_iso"),
                end_iso=args.get("end_iso"),
                reason=args.get("reason"),
            )
        if t == "get_doctor_stats":
            return tools.get_doctor_stats(
                doctor_name=args.get("doctor_name"),
                ref_date_str=args.get("ref_date"),
            )
        raise HTTPException(status_code=400, detail="Unknown tool")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
