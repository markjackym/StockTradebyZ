"""
scheduler/runner.py
后台调度守护进程 — 监听手动触发 + APScheduler 定时执行 pipeline
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from scheduler.state import (
    consume_trigger,
    get_email_config,
    get_pipeline_status,
    get_schedule_config,
    set_pipeline_status,
    append_log_line,
    append_run_log,
)
from scheduler.notifier import send_email, build_result_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
log = logging.getLogger("scheduler.runner")

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

STEPS = [
    ("1/4  拉取 K 线数据", [PYTHON, "-m", "pipeline.fetch_kline"]),
    ("2/4  量化初选", [PYTHON, "-m", "pipeline.cli", "preselect"]),
    ("3/4  导出 K 线图", [PYTHON, str(ROOT / "dashboard" / "export_kline_charts.py")]),
    ("4/4  LLM 图表分析", [PYTHON, str(ROOT / "agent" / "llm_review.py")]),
]

JOB_ID = "pipeline_cron"


def _run_pipeline(skip_fetch: bool = False, start_from: int = 1) -> None:
    status = get_pipeline_status()
    if status.get("state") == "running":
        log.warning("Pipeline 已在运行中，跳过本次触发")
        return

    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_pipeline_status(
        state="running",
        current_step="准备中",
        progress=0,
        started_at=started,
        finished_at="",
        error="",
        log_tail=[],
    )

    total_steps = len(STEPS)
    success = True
    error_msg = ""

    for i, (name, cmd) in enumerate(STEPS):
        step_num = i + 1
        if skip_fetch and step_num == 1:
            continue
        if step_num < start_from:
            continue

        pct = int((step_num - 1) / total_steps * 100)
        set_pipeline_status(current_step=name, progress=pct)
        append_log_line(f"\n{'='*50}")
        append_log_line(f"[步骤] {name}")
        append_log_line(f"  命令: {' '.join(cmd)}")
        append_log_line(f"{'='*50}")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:
                append_log_line(line)
            proc.wait()
            if proc.returncode != 0:
                error_msg = f"步骤 {name} 返回非零退出码 {proc.returncode}"
                append_log_line(f"[ERROR] {error_msg}")
                success = False
                break
        except Exception as e:
            error_msg = f"步骤 {name} 异常: {e}"
            append_log_line(f"[ERROR] {error_msg}")
            success = False
            break

    finished = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    final_state = "success" if success else "failed"
    set_pipeline_status(
        state=final_state,
        progress=100 if success else get_pipeline_status().get("progress", 0),
        current_step="完成" if success else f"失败: {error_msg}",
        finished_at=finished,
        error=error_msg,
    )

    # 追加运行记录
    rec_count = 0
    try:
        cand_file = ROOT / "data" / "candidates" / "candidates_latest.json"
        if cand_file.exists():
            pick_date = json.loads(cand_file.read_text("utf-8")).get("pick_date", "")
            sug_file = ROOT / "data" / "review" / pick_date / "suggestion.json"
            if sug_file.exists():
                sug = json.loads(sug_file.read_text("utf-8"))
                rec_count = len(sug.get("recommendations", []))
    except Exception:
        pass

    duration = ""
    try:
        t0 = datetime.strptime(started, "%Y-%m-%d %H:%M:%S")
        t1 = datetime.strptime(finished, "%Y-%m-%d %H:%M:%S")
        secs = int((t1 - t0).total_seconds())
        duration = f"{secs // 60}m{secs % 60}s"
    except Exception:
        pass

    append_run_log({
        "time": started,
        "state": final_state,
        "duration": duration,
        "recommendations": rec_count,
        "error": error_msg,
    })

    # 发送邮件通知
    _try_send_email(success, pick_date if success else "")


def _try_send_email(success: bool, pick_date: str) -> None:
    email_cfg = get_email_config()
    if not email_cfg.get("enabled"):
        return

    if success and pick_date:
        sug_file = ROOT / "data" / "review" / pick_date / "suggestion.json"
        if sug_file.exists():
            sug = json.loads(sug_file.read_text("utf-8"))
            html = build_result_email(pick_date, sug)
            send_email(f"AgentTrader 选股报告 {pick_date}", html, email_cfg)
            return

    # 失败通知
    send_email(
        "AgentTrader 流程运行失败",
        "<p style='color:#e74c3c;'>Pipeline 运行失败，请登录 Dashboard 查看日志。</p>",
        email_cfg,
    )


def _scheduled_run() -> None:
    log.info("定时任务触发 pipeline")
    cfg = get_schedule_config()
    _run_pipeline(
        skip_fetch=cfg.get("skip_fetch", False),
        start_from=cfg.get("start_from", 1),
    )


def _sync_schedule(scheduler: BackgroundScheduler) -> None:
    cfg = get_schedule_config()
    existing = scheduler.get_job(JOB_ID)

    if not cfg.get("enabled"):
        if existing:
            scheduler.remove_job(JOB_ID)
            log.info("已移除定时任务")
        return

    hour = cfg.get("hour", 18)
    minute = cfg.get("minute", 0)
    days = cfg.get("days", "mon-fri")

    if days == "mon-fri":
        dow = "mon-fri"
    elif days == "daily":
        dow = "*"
    elif days == "custom":
        custom = cfg.get("custom_days", [])
        if not custom:
            dow = "mon-fri"
        else:
            day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            dow = ",".join(day_names[d] for d in custom if 0 <= d <= 6)
    else:
        dow = "mon-fri"

    trigger = CronTrigger(hour=hour, minute=minute, day_of_week=dow)

    if existing:
        scheduler.reschedule_job(JOB_ID, trigger=trigger)
        log.info("更新定时任务: %02d:%02d %s", hour, minute, dow)
    else:
        scheduler.add_job(_scheduled_run, trigger, id=JOB_ID, replace_existing=True)
        log.info("添加定时任务: %02d:%02d %s", hour, minute, dow)


def main() -> None:
    log.info("Scheduler daemon 启动")

    scheduler = BackgroundScheduler()
    scheduler.start()

    # 加载定时任务配置的时间戳
    last_schedule_sync = 0.0

    try:
        while True:
            # 1) 检查手动触发
            trigger = consume_trigger()
            if trigger:
                log.info("收到手动触发: %s", trigger)
                _run_pipeline(
                    skip_fetch=trigger.get("skip_fetch", False),
                    start_from=trigger.get("start_from", 1),
                )

            # 2) 每 10 秒同步一次定时任务配置
            now = time.time()
            if now - last_schedule_sync > 10:
                _sync_schedule(scheduler)
                last_schedule_sync = now

            time.sleep(2)
    except KeyboardInterrupt:
        log.info("Scheduler daemon 收到中断信号，退出")
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
