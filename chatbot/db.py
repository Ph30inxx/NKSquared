"""Shared psycopg2 connection factory for all chatbot tools."""
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor

from chatbot.config import DB_URL_SYNC


@contextmanager
def get_conn():
    conn = psycopg2.connect(DB_URL_SYNC)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(conn):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cur
    finally:
        cur.close()
