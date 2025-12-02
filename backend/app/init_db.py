from .db import Base, engine
from . import models  # noqa: F401

def init():
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully")

if __name__ == "__main__":
    init()
