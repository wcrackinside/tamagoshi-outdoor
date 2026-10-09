import os, tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="tamagoshi-test-"), "test.db")

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)
