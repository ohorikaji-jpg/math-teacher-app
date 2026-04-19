from datetime import datetime, timedelta

import pandas as pd

from core.db import _connect


def get_image_stats() -> dict:
    """画像付き質問の割合を返す"""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total, COALESCE(SUM(has_image), 0) AS with_image FROM questions"
            )
            row = cur.fetchone()
    total = row["total"] or 0
    with_image = int(row["with_image"] or 0)
    return {
        "total": total,
        "with_image": with_image,
        "without_image": total - with_image,
        "ratio": round(with_image / total * 100, 1) if total > 0 else 0.0,
    }


def get_daily_question_counts(days: int = 7) -> pd.DataFrame:
    """直近N日間の日別質問件数"""
    since = (datetime.now() - timedelta(days=days)).isoformat()
    with _connect() as conn:
        df = pd.read_sql_query(
            """SELECT LEFT(timestamp, 10) AS 日付, COUNT(*) AS 件数
               FROM questions
               WHERE timestamp >= %s
               GROUP BY 日付
               ORDER BY 日付""",
            conn,
            params=[since],
        )
    return df


def get_unit_counts() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """SELECT subject_unit AS 単元, COUNT(*) AS 件数
               FROM questions
               WHERE subject_unit != ''
               GROUP BY subject_unit
               ORDER BY 件数 DESC""",
            conn,
        )
    return df


def get_error_type_counts() -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            """SELECT error_type_estimate AS つまずき種別, COUNT(*) AS 件数
               FROM questions
               WHERE error_type_estimate != ''
               GROUP BY error_type_estimate
               ORDER BY 件数 DESC""",
            conn,
        )
    return df


def get_recent_trends(days: int = 7) -> pd.DataFrame:
    since = (datetime.now() - timedelta(days=days)).isoformat()
    with _connect() as conn:
        df = pd.read_sql_query(
            """SELECT subject_unit AS 単元, COUNT(*) AS 件数
               FROM questions
               WHERE timestamp >= %s AND subject_unit != ''
               GROUP BY subject_unit
               ORDER BY 件数 DESC""",
            conn,
            params=[since],
        )
    return df


def get_follow_up_suggestions(n: int = 5) -> list[dict]:
    """授業でフォローすべき（単元 × つまずき）の上位を返す"""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT subject_unit, error_type_estimate, COUNT(*) AS cnt
                   FROM questions
                   WHERE subject_unit != '' AND error_type_estimate != ''
                   GROUP BY subject_unit, error_type_estimate
                   ORDER BY cnt DESC
                   LIMIT %s""",
                (n,),
            )
            return [dict(r) for r in cur.fetchall()]
