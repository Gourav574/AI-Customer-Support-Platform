import os
from pathlib import Path
import pytest

DB_PATH=Path(__file__).parent/"test_support.db"
os.environ["DATABASE_URL"]=f"sqlite:///{DB_PATH.as_posix()}"
os.environ["SECRET_KEY"]="pytest-secret-key-with-enough-length"
os.environ["UPLOAD_DIR"]=str(Path(__file__).parent/"uploads")
os.environ["SEED_DEMO"]="false"

@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.database import Base, engine
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)

def register(client,email="customer@test.example",role=None):
    r=client.post("/api/auth/register",json={"name":"Test Customer","email":email,"password":"SecurePassword123!"})
    assert r.status_code==201
    data=r.json()
    if role:
        from backend.app.database import SessionLocal
        from backend.app.models import User
        db=SessionLocal();u=db.get(User,data['user']['id']);u.role=role;db.commit();db.close()
    return data

@pytest.fixture()
def customer(client):
    data=register(client);client.headers.update({"Authorization":f"Bearer {data['access_token']}"});return data
