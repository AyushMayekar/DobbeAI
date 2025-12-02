from app.db import SessionLocal
from app.models import Doctor

def seed():
    db = SessionLocal()
    try:
        existing = db.query(Doctor).filter(Doctor.name == "Dr. Ahuja").first()
        if existing:
            print("Doctor already exists:", existing.name)
            return
        dr = Doctor(name="Dr. Ahuja", specialization="General Physician")
        db.add(dr)
        db.commit()
        print("Seeded Dr. Ahuja (id={})".format(dr.id))
    finally:
        db.close()

if __name__ == "__main__":
    seed()
