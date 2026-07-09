"""Tests for Qwen token expiry helpers."""
from __future__ import annotations

import base64
import json
import time

import pytest

from src.platforms.qwen.accounts import Account
from src.platforms.qwen.core.auth import AuthMixin, _jwt_expires_at
from src.platforms.qwen.core.endpoints import TOKEN_EXPIRY_MARGIN, TOKEN_LIFETIME


def _make_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": exp}).encode("utf-8")
    ).decode().rstrip("=")
    return f"{header}.{payload}.sig"


class _AuthProbe(AuthMixin):
    def __init__(self) -> None:
        self._account_states = {}
        self._cookies = {}
        self._closing = False

    def _rebuild_candidates(self) -> None:
        return None


@pytest.fixture
def auth_probe() -> _AuthProbe:
    return _AuthProbe()


def test_missing_expiry_metadata_is_treated_as_expired(auth_probe: _AuthProbe) -> None:
    account = Account(username="a@example.com", password="secret", token="tok", is_login=True)
    auth_probe._account_states[account.username] = account
    assert auth_probe._is_token_expired(account) is True


def test_token_inside_lifetime_is_valid(auth_probe: _AuthProbe) -> None:
    now = time.time()
    account = Account(
        username="a@example.com",
        password="secret",
        token="tok",
        token_expires=now + TOKEN_LIFETIME,
        last_login=now,
        is_login=True,
    )
    assert auth_probe._is_token_expired(account) is False


def test_token_past_margin_is_expired(auth_probe: _AuthProbe) -> None:
    now = time.time()
    account = Account(
        username="a@example.com",
        password="secret",
        token="tok",
        token_expires=now + TOKEN_EXPIRY_MARGIN - 1,
        is_login=True,
    )
    assert auth_probe._is_token_expired(account) is True


def test_sync_expired_account_states_clears_login(auth_probe: _AuthProbe) -> None:
    account = Account(
        username="a@example.com",
        password="secret",
        token="tok",
        token_expires=time.time() - 10,
        is_login=True,
    )
    auth_probe._account_states[account.username] = account
    assert auth_probe._sync_expired_account_states() is True
    assert account.is_login is False
    assert account.token == ""


def test_jwt_exp_past_marks_account_expired_even_if_local_expires_future(
    auth_probe: _AuthProbe,
) -> None:
    future = time.time() + TOKEN_LIFETIME
    token = _make_jwt(int(time.time()) - 120)
    account = Account(
        username="a@example.com",
        password="secret",
        token=token,
        token_expires=future,
        is_login=True,
    )
    auth_probe._account_states[account.username] = account
    assert auth_probe._is_token_expired(account) is True
    assert auth_probe._sync_expired_account_states() is True
    assert account.is_login is False
    assert account.token == ""


def test_jwt_exp_future_is_valid(auth_probe: _AuthProbe) -> None:
    token = _make_jwt(int(time.time()) + 3600)
    account = Account(
        username="a@example.com",
        password="secret",
        token=token,
        token_expires=time.time() - 10,
        is_login=True,
    )
    assert auth_probe._is_token_expired(account) is False
    assert _jwt_expires_at(token) > time.time()
