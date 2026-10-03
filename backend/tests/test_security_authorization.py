"""Offline regression tests: real JWT/ORM/HTTP gates, no Proxmox connection.

Run from backend: python -m pytest tests/test_security_authorization.py
"""
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'test.db')
os.environ['SECRET_KEY'] = 'offline-test-signing-key-not-for-production'

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user, get_access_token_user
from app.api import console, cluster
from app.api.host_permissions import authorize_host_request, require_host_access
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token
from app.models import Base, User, UserRole, ProxmoxHost, UserHostPermission


@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            User(id=1, username='viewer', email='viewer@test.invalid', hashed_password='unused', role=UserRole.VIEWER),
            User(id=2, username='operator', email='operator@test.invalid', hashed_password='unused', role=UserRole.OPERATOR),
            User(id=3, username='admin', email='admin@test.invalid', hashed_password='unused', role=UserRole.ADMIN),
            ProxmoxHost(id=1, name='assigned', hostname='host.invalid', username='root@pam'),
            ProxmoxHost(id=2, name='unassigned', hostname='other.invalid', username='root@pam'),
            UserHostPermission(user_id=1, host_id=1, can_view=True, can_manage=False, can_admin=False),
            UserHostPermission(user_id=2, host_id=1, can_view=True, can_manage=True, can_admin=False),
        ])
        session.commit()
        yield session
    engine.dispose()


def token(username, version=0):
    return create_access_token({'sub': username, 'tv': version})


@pytest.fixture
def client(db):
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db

    @app.get('/me')
    def me(user=Depends(get_current_user)):
        return {'username': user.username}

    @app.api_route('/hosts/{host_id}', methods=['GET', 'POST'], dependencies=[Depends(authorize_host_request)])
    def host(host_id: int):
        return {'host_id': host_id}

    app.include_router(console.router)
    app.include_router(cluster.router, prefix='/cluster')
    return TestClient(app)


def test_refresh_tokens_cannot_authorize_api_calls(client):
    headers = {'Authorization': 'Bearer ' + create_refresh_token({'sub': 'admin', 'tv': 0})}
    assert client.get('/me', headers=headers).status_code == 401
    assert client.get('/me', headers={'Authorization': 'Bearer ' + token('admin')}).status_code == 200


def test_password_revocation_and_disabled_accounts(db, client):
    headers = {'Authorization': 'Bearer ' + token('admin')}
    user = db.get(User, 3)
    user.token_version = 1
    db.commit()
    assert client.get('/me', headers=headers).status_code == 401
    assert get_access_token_user(token('admin', 1), db) is user
    user.is_active = False
    db.commit()
    assert get_access_token_user(token('admin', 1), db) is None


@pytest.mark.parametrize('name,host,method,status', [
    ('viewer', 1, 'GET', 200), ('viewer', 1, 'POST', 403),
    ('viewer', 2, 'GET', 403), ('operator', 1, 'POST', 200),
    ('operator', 2, 'POST', 403), ('admin', 2, 'POST', 200),
])
def test_host_permissions_http(client, name, host, method, status):
    result = client.request(method, f'/hosts/{host}', headers={'Authorization': 'Bearer ' + token(name)})
    assert result.status_code == status


@pytest.mark.asyncio
async def test_console_checks_token_version_and_type(db):
    assert await console._authenticate(create_refresh_token({'sub': 'admin', 'tv': 0}), db) is None
    db.get(User, 3).token_version = 2
    db.commit()
    assert await console._authenticate(token('admin'), db) is None
    assert await console._authenticate(token('admin', 2), db) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize('username,host_id', [('viewer', 1), ('operator', 1), ('operator', 2)])
async def test_node_console_denies_before_connecting(db, monkeypatch, username, host_id):
    monkeypatch.setattr(console, '_get_db', lambda: db)
    def forbidden_connection(*args, **kwargs):
        pytest.fail('Denied user reached a privileged Proxmox connection')
    monkeypatch.setattr(console, 'ProxmoxService', forbidden_connection)
    ws = SimpleNamespace(close=AsyncMock())
    await console.node_terminal_proxy(ws, host_id, 'test-node', token(username))
    assert ws.close.call_args.kwargs['code'] == 4403


def test_node_shell_requires_explicit_host_admin(db):
    user = db.get(User, 2)
    with pytest.raises(HTTPException):
        require_host_access(db, user, 1, 'admin')
    permission = db.query(UserHostPermission).filter_by(user_id=2, host_id=1).one()
    permission.can_admin = True
    db.commit()
    require_host_access(db, user, 1, 'admin')


def test_cluster_join_material_requires_admin(client, monkeypatch):
    monkeypatch.setattr(cluster, '_pve', lambda host: SimpleNamespace(
        cluster=SimpleNamespace(config=SimpleNamespace(join=SimpleNamespace(
            get=lambda: {'nodelist': [], 'totem': 'synthetic-test-material'})))))
    for username in ['viewer', 'operator']:
        assert client.get('/cluster/1/config/join', headers={
            'Authorization': 'Bearer ' + token(username)}).status_code == 403
    assert client.get('/cluster/1/config/join', headers={
        'Authorization': 'Bearer ' + token('admin')}).status_code == 200


def test_tokens_are_unique_and_tls_verification_is_honored():
    assert token('admin') != token('admin')
    assert create_refresh_token({'sub': 'admin'}) != create_refresh_token({'sub': 'admin'})
    import ssl
    assert console._make_ssl_context(True).verify_mode == ssl.CERT_REQUIRED
    assert console._make_ssl_context(False).verify_mode == ssl.CERT_NONE
