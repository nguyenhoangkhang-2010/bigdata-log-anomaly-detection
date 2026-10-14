import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories.demo import DemoRepository


@pytest.fixture(scope="session")
def repo() -> DemoRepository:
    return DemoRepository(seed=7, n_blocks=1500)  # nhỏ hơn mặc định cho test nhanh


@pytest.fixture(scope="session")
def client(repo):
    app = create_app(Settings(), repo=repo)
    with TestClient(app) as c:
        yield c
