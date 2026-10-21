"""Resolve current permissions from PostgreSQL, never from stale role claims."""
from flask import g, abort
from repositories.user_repository import get_user_by_id

ROLES = {'admin', 'editor', 'viewer'}


def resolve_session(payload):
    if not payload or type(payload.get('uid')) is not int:
        return None
    user = get_user_by_id(payload['uid'])
    if not user or not user['is_active'] or user['role'] not in ROLES or user['session_version'] != payload.get('ver', 0):
        return None
    return user


def require_admin():
    if g.current_user['role'] != 'admin':
        abort(403, description='Доступно только администратору.')


def can_edit_map(record):
    return g.current_user['role'] == 'admin' or (
        g.current_user['role'] == 'editor' and record['owner_id'] == g.current_user_id)
