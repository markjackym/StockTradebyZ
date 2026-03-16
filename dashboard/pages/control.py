"""
dashboard/pages/control.py
控制中心 — 运行/调度/邮件配置
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from scheduler.state import (
    get_pipeline_status,
    get_schedule_config,
    set_schedule_config,
    get_email_config,
    set_email_config,
    get_run_logs,
    create_trigger,
)
from scheduler.notifier import send_email


def render() -> None:
    st.markdown("## 控制中心")

    # ══════════════════════════════════════════════════════════════════════
    # 1. 流程运行区
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("### 流程运行")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        skip_fetch = st.checkbox("跳过行情下载 (skip-fetch)", value=False)
    with col2:
        start_from = st.selectbox("从第 N 步开始", [1, 2, 3, 4], index=0)
    with col3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("立即运行全流程", type="primary", use_container_width=True):
            create_trigger(skip_fetch=skip_fetch, start_from=start_from)
            st.toast("已触发 Pipeline 运行！", icon="🚀")

    # ── 实时状态 ──────────────────────────────────────────────────────────
    @st.fragment(run_every=3)
    def _status_fragment():
        status = get_pipeline_status()
        state = status.get("state", "idle")

        state_labels = {
            "idle": ("空闲", "off"),
            "running": ("运行中", "running"),
            "success": ("成功", "complete"),
            "failed": ("失败", "error"),
        }
        label, icon = state_labels.get(state, ("未知", "off"))

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("状态", label)
        col_b.metric("当前步骤", status.get("current_step", "-") or "-")
        col_c.metric("进度", f"{status.get('progress', 0)}%")

        if state == "running":
            st.progress(status.get("progress", 0) / 100)

        if status.get("error"):
            st.error(status["error"])

        # 日志输出
        log_tail = status.get("log_tail", [])
        if log_tail:
            with st.expander("运行日志", expanded=(state == "running")):
                st.code("\n".join(log_tail[-50:]), language="text")

    _status_fragment()

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════
    # 2. 定时任务区
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("### 定时任务")

    sched_cfg = get_schedule_config()

    sched_enabled = st.toggle("启用定时调度", value=sched_cfg.get("enabled", False))

    col_h, col_m = st.columns(2)
    with col_h:
        sched_hour = st.number_input("运行时间（小时）", min_value=0, max_value=23,
                                     value=sched_cfg.get("hour", 18))
    with col_m:
        sched_minute = st.number_input("运行时间（分钟）", min_value=0, max_value=59,
                                       value=sched_cfg.get("minute", 0))

    days_options = {"交易日 (Mon-Fri)": "mon-fri", "每天": "daily", "自选": "custom"}
    days_label = st.selectbox(
        "运行日期",
        list(days_options.keys()),
        index=list(days_options.values()).index(sched_cfg.get("days", "mon-fri")),
    )
    sched_days = days_options[days_label]

    custom_days = []
    if sched_days == "custom":
        day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        selected = st.multiselect("选择运行日", day_names,
                                  default=[day_names[d] for d in sched_cfg.get("custom_days", [])])
        custom_days = [day_names.index(d) for d in selected]

    sched_skip_fetch = st.checkbox("定时任务跳过行情下载", value=sched_cfg.get("skip_fetch", False),
                                   key="sched_skip_fetch")
    sched_start_from = st.selectbox("定时任务从第 N 步开始", [1, 2, 3, 4],
                                    index=sched_cfg.get("start_from", 1) - 1,
                                    key="sched_start_from")

    if st.button("保存定时任务配置"):
        new_cfg = {
            "enabled": sched_enabled,
            "hour": int(sched_hour),
            "minute": int(sched_minute),
            "days": sched_days,
            "custom_days": custom_days,
            "skip_fetch": sched_skip_fetch,
            "start_from": int(sched_start_from),
        }
        set_schedule_config(new_cfg)
        st.success("定时任务配置已保存")

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════
    # 3. 邮件通知区
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("### 邮件通知")

    email_cfg = get_email_config()

    email_enabled = st.toggle("启用邮件通知", value=email_cfg.get("enabled", False))

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        smtp_host = st.text_input("SMTP 服务器", value=email_cfg.get("smtp_host", ""))
        smtp_user = st.text_input("发件人邮箱", value=email_cfg.get("smtp_user", ""))
        smtp_to = st.text_input("收件人（逗号分隔）", value=email_cfg.get("recipients", ""))
    with col_e2:
        smtp_port = st.number_input("SMTP 端口", value=int(email_cfg.get("smtp_port", 465)),
                                    min_value=1, max_value=65535)
        smtp_pass = st.text_input("邮箱授权码", value=email_cfg.get("smtp_pass", ""), type="password")

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("保存邮件配置"):
            new_email = {
                "enabled": email_enabled,
                "smtp_host": smtp_host,
                "smtp_port": int(smtp_port),
                "smtp_user": smtp_user,
                "smtp_pass": smtp_pass,
                "recipients": smtp_to,
            }
            set_email_config(new_email)
            st.success("邮件配置已保存")
    with btn_col2:
        if st.button("发送测试邮件"):
            test_cfg = {
                "smtp_host": smtp_host,
                "smtp_port": int(smtp_port),
                "smtp_user": smtp_user,
                "smtp_pass": smtp_pass,
                "recipients": smtp_to,
            }
            ok = send_email(
                "AgentTrader 测试邮件",
                "<h3>测试成功！</h3><p>如果您收到这封邮件，说明 SMTP 配置正确。</p>",
                test_cfg,
            )
            if ok:
                st.success("测试邮件发送成功！")
            else:
                st.error("测试邮件发送失败，请检查配置。")

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════
    # 4. 运行历史
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("### 运行历史")

    @st.fragment(run_every=10)
    def _history_fragment():
        runs = get_run_logs(20)
        if not runs:
            st.info("暂无运行记录")
            return

        import pandas as pd  # noqa: F811
        df = pd.DataFrame(runs)
        col_map = {
            "time": "运行时间",
            "state": "状态",
            "duration": "耗时",
            "recommendations": "推荐数",
            "error": "错误",
        }
        display_cols = [c for c in col_map if c in df.columns]
        df = df[display_cols].rename(columns=col_map)
        st.dataframe(df, use_container_width=True, hide_index=True)

    _history_fragment()
