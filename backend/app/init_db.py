# backend/app/init_db.py
"""
Create DB tables from models. Run:
python -m app.init_db
"""
from .db import Base, engine
# import models so SQLAlchemy knows about them
from . import models  # noqa: F401

def init():
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully")

if __name__ == "__main__":
    init()
