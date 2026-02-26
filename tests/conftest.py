from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import deps
from app.core.limiter import limiter as app_limiter
from app.core.security import get_password_hash
from app.main import app
from app.models import User

TEST_DB_URL = "sqlite:///./test_infrascope.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


app.router.lifespan_context = _noop_lifespan


@pytest.fixture(autouse=True)
def _clean_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def db_session():
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session, monkeypatch: pytest.MonkeyPatch):
    async def _not_blacklisted(_jti: str) -> bool:
        return False

    async def _blacklist_token(_jti: str, _ttl: int) -> None:
        return None

    monkeypatch.setattr(deps, "is_token_blacklisted", _not_blacklisted)
    from app.api.routes import auth as auth_routes

    monkeypatch.setattr(auth_routes, "blacklist_token", _blacklist_token)
    def _fake_check_request_limit(request, _endpoint, _in_middleware=True):
        request.state.view_rate_limit = None
        return None

    monkeypatch.setattr(app_limiter, "_check_request_limit", _fake_check_request_limit)

    def override_get_db():
        yield db_session

    app.dependency_overrides[deps.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("Pass1234"),
        full_name="Admin",
        is_superuser=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_user(db_session):
    user = User(
        email="user@example.com",
        hashed_password=get_password_hash("Pass1234"),
        full_name="User",
        is_superuser=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(client: TestClient, admin_user: User):
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "Pass1234"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def user_token(client: TestClient, regular_user: User):
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": regular_user.email, "password": "Pass1234"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]
