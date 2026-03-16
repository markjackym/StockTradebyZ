"""
dashboard/pages/results.py
推荐结果页面 — 查看 LLM 评分结果
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))


def _find_latest_suggestion() -> tuple[str, dict | None]:
    """查找最新的 suggestion.json，返回 (pick_date, suggestion_data)"""
    candidates_file = _ROOT / "data" / "candidates" / "candidates_latest.json"
    if not candidates_file.exists():
        return "", None

    try:
        with open(candidates_file, "r", encoding="utf-8") as f:
            pick_date = json.load(f).get("pick_date", "")
    except Exception:
        return "", None

    if not pick_date:
        return "", None

    suggestion_file = _ROOT / "data" / "review" / pick_date / "suggestion.json"
    if not suggestion_file.exists():
        return pick_date, None

    try:
        with open(suggestion_file, "r", encoding="utf-8") as f:
            return pick_date, json.load(f)
    except Exception:
        return pick_date, None


def _load_stock_review(pick_date: str, code: str) -> dict | None:
    review_file = _ROOT / "data" / "review" / pick_date / f"{code}.json"
    if not review_file.exists():
        return None
    try:
        with open(review_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def render() -> None:
    st.markdown("## 推荐结果")

    # 支持查看历史日期
    review_dir = _ROOT / "data" / "review"
    available_dates = sorted(
        [d.name for d in review_dir.iterdir() if d.is_dir() and (d / "suggestion.json").exists()],
        reverse=True,
    ) if review_dir.exists() else []

    if not available_dates:
        st.warning("尚无评分结果。请先运行完整流程。")
        return

    pick_date = st.selectbox("选择日期", available_dates, index=0)

    suggestion_file = review_dir / pick_date / "suggestion.json"
    try:
        with open(suggestion_file, "r", encoding="utf-8") as f:
            suggestion = json.load(f)
    except Exception:
        st.error(f"无法读取 {suggestion_file}")
        return

    # ── 概要 ──────────────────────────────────────────────────────────────
    total = suggestion.get("total_reviewed", 0)
    threshold = suggestion.get("min_score_threshold", 0)
    recs = suggestion.get("recommendations", [])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("选股日期", pick_date)
    col2.metric("评审总数", f"{total} 只")
    col3.metric("推荐门槛", f"score >= {threshold}")
    col4.metric("推荐数量", f"{len(recs)} 只")

    if not recs:
        st.info("暂无达标推荐股票。")
        return

    # ── 推荐表格 ──────────────────────────────────────────────────────────
    st.markdown("### 推荐列表")

    df = pd.DataFrame(recs)
    col_map = {
        "rank": "排名",
        "code": "代码",
        "total_score": "总分",
        "signal_type": "信号",
        "verdict": "研判",
        "comment": "备注",
    }
    display_cols = [c for c in col_map if c in df.columns]
    df_display = df[display_cols].rename(columns=col_map)
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── 单股详情 ──────────────────────────────────────────────────────────
    st.markdown("### 单股详情")

    stock_codes = [r.get("code", "") for r in recs]
    selected_code = st.selectbox("选择股票查看详细评分", stock_codes)

    if selected_code:
        review = _load_stock_review(pick_date, selected_code)
        if review:
            # 评分卡片
            scores = review.get("scores", {})
            if scores:
                score_cols = st.columns(len(scores))
                score_labels = {
                    "trend_structure": "趋势结构",
                    "price_position": "价格位置",
                    "volume_behavior": "量价行为",
                    "previous_abnormal_move": "异动信号",
                }
                for col, (key, val) in zip(score_cols, scores.items()):
                    label = score_labels.get(key, key)
                    col.metric(label, f"{val}/5")

            st.markdown(f"**总分**: {review.get('total_score', '-')} / 5")
            st.markdown(f"**信号类型**: {review.get('signal_type', '-')}")
            st.markdown(f"**研判**: {review.get('verdict', '-')}")
            st.markdown(f"**综合评语**: {review.get('comment', '-')}")

            # 各维度分析
            reasoning_fields = [
                ("trend_reasoning", "趋势分析"),
                ("position_reasoning", "位置分析"),
                ("volume_reasoning", "量能分析"),
                ("abnormal_move_reasoning", "异动分析"),
                ("signal_reasoning", "信号分析"),
            ]
            for field, title in reasoning_fields:
                text = review.get(field, "")
                if text:
                    with st.expander(title):
                        st.write(text)

            # 完整 JSON
            with st.expander("完整 JSON 数据"):
                st.json(review)
        else:
            st.warning(f"未找到 {selected_code} 的评分数据")

        # K 线图（如果存在）
        kline_dir = _ROOT / "data" / "kline" / pick_date
        kline_img = kline_dir / f"{selected_code}_day.jpg"
        if kline_img.exists():
            st.markdown("#### K 线图")
            st.image(str(kline_img), caption=f"{selected_code} 日线图", use_container_width=True)
