from pathlib import Path

import pandas as pd
import streamlit as st

from core.ai import generate_followup_suggestions
from core.analysis import (
    get_daily_question_counts,
    get_error_type_counts,
    get_follow_up_suggestions,
    get_image_stats,
    get_recent_trends,
    get_unit_counts,
)
from core.db import get_all_units, get_questions, init_db, update_teacher_note

init_db()

col_title, col_logout = st.columns([6, 1])
with col_title:
    st.title("📊 教師ダッシュボード")
with col_logout:
    st.write("")
    if st.button("ログアウト", use_container_width=True):
        st.session_state.teacher_authenticated = False
        st.rerun()

tab_list, tab_analysis = st.tabs(["質問一覧", "分析"])

# ──────────────────────────────────────────────
# タブ1: 質問一覧
# ──────────────────────────────────────────────
with tab_list:
    col1, col2 = st.columns([2, 1])
    with col1:
        search = st.text_input("キーワード検索", placeholder="質問・回答内を検索")
    with col2:
        unit_options = ["（全単元）"] + get_all_units()
        unit_filter = st.selectbox("単元絞り込み", unit_options)

    unit_q = "" if unit_filter == "（全単元）" else unit_filter
    questions = get_questions(search=search, unit=unit_q)

    st.caption(f"{len(questions)} 件")

    if not questions:
        st.info("質問がまだありません。生徒画面から質問してみてください。")
    else:
        df = pd.DataFrame(questions)

        # 一覧テーブル（概要のみ）
        df_view = df[["id", "timestamp", "subject_unit", "difficulty_estimate", "error_type_estimate", "question"]].copy()
        df_view.columns = ["ID", "日時", "単元", "難易度", "つまずき", "質問（先頭）"]
        df_view["日時"] = df_view["日時"].str[:16].str.replace("T", " ")
        df_view["質問（先頭）"] = df_view["質問（先頭）"].str[:40] + "…"
        # 画像アイコン列を追加
        df_view.insert(1, "画像", df["has_image"].apply(lambda v: "📎" if v else ""))

        event = st.dataframe(
            df_view,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
        )

        # 行選択で詳細表示
        selected_rows = event.selection.get("rows", [])
        if selected_rows:
            row = questions[selected_rows[0]]
            st.divider()
            st.subheader(f"詳細 — ID: {row['id']}")

            col_q, col_meta = st.columns([2, 1])
            with col_q:
                st.write("**質問**")
                st.info(row["question"] or "（テキストなし）")
                # 画像プレビュー
                if row.get("has_image") and row.get("image_path"):
                    img_path = Path(row["image_path"])
                    if img_path.exists():
                        st.write("**添付画像**")
                        st.image(str(img_path), caption=row.get("image_filename", ""), use_container_width=False, width=480)
                        if row.get("image_analysis_summary"):
                            st.caption(f"画像サマリ: {row['image_analysis_summary']}")
                    else:
                        st.warning(f"画像ファイルが見つかりません: {row.get('image_filename', '')}")
                st.write("**回答**")
                st.markdown(row["answer"])
            with col_meta:
                st.write("**メタ情報**")
                st.write(f"- 日時: {row['timestamp'][:16].replace('T', ' ')}")
                st.write(f"- 単元: {row['subject_unit'] or '未分類'}")
                st.write(f"- 難易度: {row['difficulty_estimate'] or '—'}")
                st.write(f"- つまずき: {row['error_type_estimate'] or '—'}")
                st.write(f"- ユーザーID: `{row['user_id']}`")
                if row.get("has_image"):
                    st.write(f"- 画像: 📎 `{row.get('image_filename', '')}`")

                st.write("**教師メモ**")
                note = st.text_area(
                    "メモ（授業フォロー用）",
                    value=row["teacher_note"] or "",
                    key=f"note_{row['id']}",
                    label_visibility="collapsed",
                )
                if st.button("保存", key=f"save_{row['id']}"):
                    update_teacher_note(row["id"], note)
                    st.success("メモを保存しました")


# ──────────────────────────────────────────────
# タブ2: 分析
# ──────────────────────────────────────────────
with tab_analysis:

    # ── 0. サマリ指標（最上段） ──────────────────
    img_stats = get_image_stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("総質問数", f"{img_stats['total']} 件")
    m2.metric("画像付き質問", f"{img_stats['with_image']} 件")
    m3.metric("画像なし質問", f"{img_stats['without_image']} 件")
    m4.metric("画像付き割合", f"{img_stats['ratio']} %")

    st.divider()

    # ── 1. 単元別ランキング & 2. つまずき種別ランキング ──
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📚 単元別 質問数ランキング")
        df_unit = get_unit_counts()
        if df_unit.empty:
            st.info("データがまだありません")
        else:
            # ランキング番号付きテーブル
            df_unit_view = df_unit.reset_index(drop=True)
            df_unit_view.index = df_unit_view.index + 1
            df_unit_view.index.name = "順位"
            st.dataframe(df_unit_view, use_container_width=True)
            st.bar_chart(df_unit.set_index("単元"))

    with col_b:
        st.subheader("⚠️ つまずき種別 ランキング")
        df_err = get_error_type_counts()
        if df_err.empty:
            st.info("データがまだありません")
        else:
            df_err_view = df_err.reset_index(drop=True)
            df_err_view.index = df_err_view.index + 1
            df_err_view.index.name = "順位"
            st.dataframe(df_err_view, use_container_width=True)
            st.bar_chart(df_err.set_index("つまずき種別"))

    st.divider()

    # ── 3. 直近7日間トレンド ──────────────────────
    st.subheader("📅 直近7日間の質問トレンド")
    col_trend_daily, col_trend_unit = st.columns(2)

    with col_trend_daily:
        st.caption("日別 質問件数")
        df_daily = get_daily_question_counts(days=7)
        if df_daily.empty:
            st.info("直近7日のデータがありません")
        else:
            st.bar_chart(df_daily.set_index("日付"))

    with col_trend_unit:
        st.caption("直近7日間 単元別件数")
        df_recent = get_recent_trends(days=7)
        if df_recent.empty:
            st.info("直近7日のデータがありません")
        else:
            st.bar_chart(df_recent.set_index("単元"))

    st.divider()

    # ── 4. 画像付き質問の割合（詳細） ────────────
    st.subheader("🖼️ 画像付き質問の内訳")
    if img_stats["total"] == 0:
        st.info("データがまだありません")
    else:
        col_pie, col_detail = st.columns([1, 2])
        with col_pie:
            df_img = pd.DataFrame({
                "種別": ["画像あり", "画像なし"],
                "件数": [img_stats["with_image"], img_stats["without_image"]],
            })
            st.dataframe(df_img, use_container_width=True, hide_index=True)
        with col_detail:
            st.metric("画像付き質問の割合", f"{img_stats['ratio']} %")
            st.progress(img_stats["ratio"] / 100)
            st.caption(
                f"全 {img_stats['total']} 件のうち {img_stats['with_image']} 件が"
                f"図・グラフ・手書き式の画像を添付した質問です。"
            )

    st.divider()

    # ── 5. AIによるフォローポイント3件 ────────────
    st.subheader("🤖 次の授業でフォローすべきポイント（AI生成）")

    raw_suggestions = get_follow_up_suggestions(n=5)
    df_unit_top = get_unit_counts().head(3)
    df_err_top  = get_error_type_counts().head(3)
    df_recent_top = get_recent_trends(days=7).head(3)

    has_data = bool(raw_suggestions) or not df_unit_top.empty

    if not has_data:
        st.info("データが蓄積されるとAIがフォローポイントを自動生成します")
    else:
        if st.button("💡 AIにフォローポイントを生成させる", use_container_width=True):
            unit_text   = df_unit_top.to_string(index=False) if not df_unit_top.empty else "データなし"
            error_text  = df_err_top.to_string(index=False)  if not df_err_top.empty  else "データなし"
            recent_text = df_recent_top.to_string(index=False) if not df_recent_top.empty else "データなし"

            with st.spinner("AIが分析中..."):
                try:
                    ai_points = generate_followup_suggestions(
                        unit_ranking=unit_text,
                        error_ranking=error_text,
                        recent_trend=recent_text,
                        image_ratio=img_stats["ratio"],
                    )
                    st.session_state["ai_followup"] = ai_points
                except Exception as e:
                    st.error(f"AI生成に失敗しました: {e}")

        points = st.session_state.get("ai_followup", [])
        if points:
            for i, p in enumerate(points, 1):
                st.markdown(
                    f"""<div style="background:#f0f7ff;border-left:4px solid #2563eb;
                    border-radius:6px;padding:10px 14px;margin-bottom:8px;">
                    <b>{i}.</b> {p}</div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("ボタンを押すとAIがデータを分析してフォローポイントを生成します。")

        st.divider()
        st.caption("📋 集計ベースの上位パターン（参考）")
        for i, s in enumerate(raw_suggestions, 1):
            st.write(
                f"{i}. **{s['subject_unit']}** — "
                f"{s['error_type_estimate']} に関する質問が **{s['cnt']}件**"
            )
