"""Authentication helpers for login and session cookies."""

import sqlite3
from secrets import token_bytes
from time import time
from base64 import b64encode, b64decode

from password_hash import hash_interface
from password_hash.providers import argon2id_provider

SESSION_DURATION_SECONDS = 60 * 60 * 24 * 7


def _encode_cookie_value(session_id: bytes) -> str:
    return b64encode(session_id).decode('ASCII')

def _decode_cookie_value(session_id: str) -> bytes:
    return b64decode(session_id.encode('ASCII'))

#returns a new session_id if the user is found
def authenticate_user(db: sqlite3.Connection, username: str, password: bytes) -> str | None:
    if not db:
        return None
    
    row = db.execute(
        """
        SELECT user_id, username, password_hash, hash_algorithm, salt
        FROM user
        WHERE username = ?
        """,
        (username,),
    ).fetchone()

    if row is None:
        return None
    
    hasher = hash_interface.password_hash_providers.get(row["hash_algorithm"], None)
    if(hasher is None):
        return None

    if(hasher.verify(password, row["password_hash"], row["salt"]) == True):
        return _issue_session_cookie(db, row["user_id"])
    
    return None


def create_user(db: sqlite3.Connection, username: str, password: bytes, phone_number: str) -> str | None:
    if not db:
        return None

    hasher = argon2id_provider.argon2id_default_provider
    hash_info = hasher.get_hash(password)

    try:
        cursor = db.execute(
            """
            INSERT INTO user (username, password_hash, hash_algorithm, salt, phone_number)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, hash_info.hash, hash_info.hasher_name, hash_info.salt, phone_number),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return None

    return _issue_session_cookie(db, cursor.lastrowid) # pyright: ignore[reportArgumentType]

#requires auth!
def _issue_session_cookie(db: sqlite3.Connection, user_id: int) -> str | None:
    if not db:
        return None
    
    expires_at = int(time()) + SESSION_DURATION_SECONDS

    #ensure session_id is unique
    while True:
        session_id = token_bytes(32)
        token = _hash_session_id(session_id)
        
        #check if it is in the db
        check = db.execute(
            "SELECT 1 FROM session_tokens WHERE session_id_hash = ? LIMIT 1",
            (token,),
        ).fetchone()
        if(check is None):
            #put it in the database
            db.execute(
                """
                INSERT INTO session_tokens (user_id, session_id_hash, expires_at)
                VALUES (?, ?, ?)
                """,
                (user_id, token, expires_at),
            )
            
            db.commit()
            
            return _encode_cookie_value(session_id)
        
def _hash_session_id(session_id: bytes) -> bytes:
    return argon2id_provider.argon2id_default_provider.get_hash_with_salt(session_id, bytes()).hash


def load_current_user(db: sqlite3.Connection, cookie_value: str | None) -> sqlite3.Row | None:
    if not cookie_value or not db:
        return None

    try:
        parsed_cookie = _decode_cookie_value(cookie_value)
    except (ValueError, UnicodeError):
        return None

    session_hash = _hash_session_id(parsed_cookie)
    now = int(time())

    return db.execute(
        """
        SELECT user_id, session_id_hash, expires_at
        FROM session_tokens
        WHERE session_id_hash = ?
          AND expires_at > ?
        """,
        (session_hash, now),
    ).fetchone()