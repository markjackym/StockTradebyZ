"""
scheduler/notifier.py
邮件通知 — 支持 SSL (465) 和 STARTTLS (587)
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def send_email(subject: str, html_body: str, config: dict) -> bool:
    host = config.get("smtp_host", "")
    port = int(config.get("smtp_port", 465))
    user = config.get("smtp_user", "")
    passwd = config.get("smtp_pass", "")
    recipients = config.get("recipients", "")

    if not all([host, user, passwd, recipients]):
        log.warning("邮件配置不完整，跳过发送")
        return False

    to_list = [r.strip() for r in recipients.split(",") if r.strip()]
    if not to_list:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as s:
                s.login(user, passwd)
                s.sendmail(user, to_list, msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(user, passwd)
                s.sendmail(user, to_list, msg.as_string())
        log.info("邮件发送成功 → %s", to_list)
        return True
    except Exception as e:
        log.error("邮件发送失败: %s", e)
        return False


def build_result_email(pick_date: str, suggestion: dict) -> str:
    recs = suggestion.get("recommendations", [])
    total = suggestion.get("total_reviewed", 0)
    threshold = suggestion.get("min_score_threshold", 0)

    rows = ""
    for r in recs:
        rows += (
            f"<tr>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;'>{r.get('rank','')}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;font-weight:bold;'>{r.get('code','')}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;color:#e74c3c;'>{r.get('total_score','')}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;'>{r.get('signal_type','')}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;'>{r.get('verdict','')}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;font-size:12px;'>{r.get('comment','')}</td>"
            f"</tr>"
        )

    if not rows:
        rows = "<tr><td colspan='6' style='padding:20px;text-align:center;color:#999;'>暂无达标推荐</td></tr>"

    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:800px;margin:0 auto;">
      <h2 style="color:#1f2328;">AgentTrader 选股报告</h2>
      <p style="color:#636c76;">
        选股日期：<b>{pick_date}</b> &nbsp;|&nbsp;
        评审总数：<b>{total}</b> 只 &nbsp;|&nbsp;
        推荐门槛：score &ge; <b>{threshold}</b> &nbsp;|&nbsp;
        推荐数量：<b style="color:#e74c3c;">{len(recs)}</b> 只
      </p>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#f6f8fa;">
            <th style="padding:8px 10px;text-align:left;border-bottom:2px solid #d0d7de;">排名</th>
            <th style="padding:8px 10px;text-align:left;border-bottom:2px solid #d0d7de;">代码</th>
            <th style="padding:8px 10px;text-align:left;border-bottom:2px solid #d0d7de;">总分</th>
            <th style="padding:8px 10px;text-align:left;border-bottom:2px solid #d0d7de;">信号</th>
            <th style="padding:8px 10px;text-align:left;border-bottom:2px solid #d0d7de;">研判</th>
            <th style="padding:8px 10px;text-align:left;border-bottom:2px solid #d0d7de;">备注</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <hr style="margin-top:20px;border:none;border-top:1px solid #eee;">
      <p style="font-size:12px;color:#999;">此邮件由 AgentTrader 自动发送</p>
    </div>
    """
