import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "questions.db"


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             TEXT    NOT NULL,
                timestamp           TEXT    NOT NULL,
                question            TEXT    NOT NULL,
                answer              TEXT    NOT NULL,
                subject_unit        TEXT    DEFAULT '',
                difficulty_estimate TEXT    DEFAULT '',
                error_type_estimate TEXT    DEFAULT '',
                teacher_note        TEXT    DEFAULT ''
            )
        """)
        # 画像対応カラムの追加（既存DBへの安全なマイグレーション）
        for col, definition in [
            ("has_image",              "INTEGER DEFAULT 0"),
            ("image_path",             "TEXT    DEFAULT ''"),
            ("image_filename",         "TEXT    DEFAULT ''"),
            ("image_analysis_summary", "TEXT    DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE questions ADD COLUMN {col} {definition}")
            except Exception:
                pass  # カラムが既に存在する場合はスキップ


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_question(record: dict) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO questions
               (user_id, timestamp, question, answer, subject_unit,
                difficulty_estimate, error_type_estimate, teacher_note,
                has_image, image_path, image_filename, image_analysis_summary)
               VALUES (:user_id, :timestamp, :question, :answer, :subject_unit,
                       :difficulty_estimate, :error_type_estimate, :teacher_note,
                       :has_image, :image_path, :image_filename, :image_analysis_summary)""",
            {
                "has_image": 0,
                "image_path": "",
                "image_filename": "",
                "image_analysis_summary": "",
                **record,
            },
        )
        return cur.lastrowid


def update_classification(record_id: int, classification: dict):
    with _connect() as conn:
        conn.execute(
            """UPDATE questions SET
               subject_unit        = :subject_unit,
               difficulty_estimate = :difficulty_estimate,
               error_type_estimate = :error_type_estimate
               WHERE id = :id""",
            {**classification, "id": record_id},
        )


def update_teacher_note(record_id: int, note: str):
    with _connect() as conn:
        conn.execute(
            "UPDATE questions SET teacher_note = ? WHERE id = ?",
            (note, record_id),
        )


def get_questions(search: str = "", unit: str = "") -> list[dict]:
    sql = "SELECT * FROM questions WHERE 1=1"
    params: list = []
    if search:
        sql += " AND (question LIKE ? OR answer LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if unit:
        sql += " AND subject_unit = ?"
        params.append(unit)
    sql += " ORDER BY timestamp DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_all_units() -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT subject_unit FROM questions WHERE subject_unit != '' ORDER BY subject_unit"
        ).fetchall()
    return [r[0] for r in rows]
