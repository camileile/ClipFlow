import pytest

from app.main import app


@pytest.fixture(autouse=True)
def reset_global_rate_limiter():
    app.state.rate_limiter.clear()
    yield
    app.state.rate_limiter.clear()
