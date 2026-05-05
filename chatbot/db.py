"""Shared psycopg2 connection pool for all chatbot tools.

Uses ThreadedConnectionPool instead of per-call psycopg2.connect() to
eliminate TCP handshake + auth overhead on every DB operation.
"""
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from chatbot.config import DB_URL_SYNC

_pool = ThreadedConnectionPool(minconn=2, maxconn=20, dsn=DB_URL_SYNC)


@contextmanager
def get_conn():
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


@contextmanager
def get_cursor(conn):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cur
    finally:
        cur.close()
