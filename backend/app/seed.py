from app.db import SessionLocal
from app.models import Doctor

DOCTORS_TO_ADD = [
    "Dr. Ahuja",
    "Dr. Mehta",
    "Dr. Sharma",
    "Dr. Roy",
    "Dr. Joy",
    "Dr. Joshi"
]

def seed():
    db = SessionLocal()
    try:
        for name in DOCTORS_TO_ADD:
            exists = db.query(Doctor).filter(Doctor.name == name).first()
            if exists:
                print(f"Doctor already exists: {name}")
                continue
            dr = Doctor(name=name, specialization="General Physician")
            db.add(dr)
            db.commit()
            print(f"Seeded {name}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
