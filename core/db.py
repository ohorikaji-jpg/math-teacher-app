import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def _get_dsn() -> str:
    # Streamlit Cloud の場合は st.secrets から取得
    try:
        import streamlit as st
        dsn = st.secrets.get("DATABASE_URL", "")
        if dsn:
            return dsn
    except Exception:
        pass
    # ローカルの場合は .env から取得
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise EnvironmentError("DATABASE_URL が設定されていません。")
    return dsn


@contextmanager
def _connect():
    conn = psycopg2.connect(_get_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id                  SERIAL PRIMARY KEY,
                    user_id             TEXT    NOT NULL,
                    timestamp           TEXT    NOT NULL,
                    question            TEXT    NOT NULL,
                    answer              TEXT    NOT NULL,
                    subject_unit        TEXT    DEFAULT '',
                    difficulty_estimate TEXT    DEFAULT '',
                    error_type_estimate TEXT    DEFAULT '',
                    teacher_note        TEXT    DEFAULT '',
                    has_image           INTEGER DEFAULT 0,
                    image_path          TEXT    DEFAULT '',
                    image_filename      TEXT    DEFAULT '',
                    image_analysis_summary TEXT DEFAULT ''
                )
            """)


def save_question(record: dict) -> int:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO questions
                   (user_id, timestamp, question, answer, subject_unit,
                    difficulty_estimate, error_type_estimate, teacher_note,
                    has_image, image_path, image_filename, image_analysis_summary)
                   VALUES (%(user_id)s, %(timestamp)s, %(question)s, %(answer)s,
                           %(subject_unit)s, %(difficulty_estimate)s,
                           %(error_type_estimate)s, %(teacher_note)s,
                           %(has_image)s, %(image_path)s, %(image_filename)s,
                           %(image_analysis_summary)s)
                   RETURNING id""",
                {
                    "has_image": 0,
                    "image_path": "",
                    "image_filename": "",
                    "image_analysis_summary": "",
                    **record,
                },
            )
            return cur.fetchone()["id"]


def update_classification(record_id: int, classification: dict):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE questions SET
                   subject_unit        = %(subject_unit)s,
                   difficulty_estimate = %(difficulty_estimate)s,
                   error_type_estimate = %(error_type_estimate)s
                   WHERE id = %(id)s""",
                {**classification, "id": record_id},
            )


def update_teacher_note(record_id: int, note: str):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE questions SET teacher_note = %s WHERE id = %s",
                (note, record_id),
            )


def get_questions(search: str = "", unit: str = "") -> list[dict]:
    sql = "SELECT * FROM questions WHERE 1=1"
    params = []
    if search:
        sql += " AND (question LIKE %s OR answer LIKE %s)"
        params += [f"%{search}%", f"%{search}%"]
    if unit:
        sql += " AND subject_unit = %s"
        params.append(unit)
    sql += " ORDER BY timestamp DESC"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def get_all_units() -> list[str]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT subject_unit FROM questions WHERE subject_unit != '' ORDER BY subject_unit"
            )
            return [r["subject_unit"] for r in cur.fetchall()]
