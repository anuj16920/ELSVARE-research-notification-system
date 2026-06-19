"""
email_service.py - Email notification service using SMTP with TLS
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailService:
    """Send paper alert emails via Gmail SMTP (or any SMTP server)."""

    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587

    def __init__(self, sender_email: str, app_password: str):
        if not sender_email or not app_password:
            raise ValueError("EMAIL_ADDRESS and EMAIL_APP_PASSWORD are required")
        self.sender = sender_email
        self.password = app_password

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def send_paper_alert(self, paper: dict, recipient: str) -> bool:
        """
        Send a formatted paper alert email.
        Returns True on success, False on failure.
        """
        subject = "🔬 NEW RESEARCH PAPER FOUND"
        body_text = self._build_plain_text(paper)
        body_html = self._build_html(paper)

        try:
            self._send(recipient, subject, body_text, body_html)
            logger.info("Email sent to %s for DOI: %s", recipient, paper.get("doi", "N/A"))
            return True
        except Exception as exc:
            logger.error("Failed to send email for DOI %s: %s", paper.get("doi"), exc)
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_plain_text(self, paper: dict) -> str:
        return (
            "NEW RESEARCH PAPER FOUND\n"
            "=" * 50 + "\n\n"
            f"Title:          {paper.get('title', 'N/A')}\n"
            f"Authors:        {paper.get('authors', 'N/A')}\n"
            f"Journal:        {paper.get('journal', 'N/A')}\n"
            f"Published Date: {paper.get('published', 'N/A')}\n"
            f"DOI:            {paper.get('doi', 'N/A')}\n"
            f"Keywords:       {paper.get('keywords', 'N/A')}\n"
            f"Paper URL:      {paper.get('url', 'N/A')}\n\n"
            + (
                f"Abstract:\n{paper.get('abstract', '')}\n\n"
                if paper.get("abstract")
                else ""
            )
            + "-" * 50 + "\n"
            f"Alert generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            "Elsevier Paper Alert Agent"
        )

    def _build_html(self, paper: dict) -> str:
        doi = paper.get("doi", "")
        url = paper.get("url", f"https://doi.org/{doi}" if doi else "#")
        abstract_html = (
            f"""
            <tr>
              <td style="padding:8px 0;color:#555;font-weight:600;width:140px;vertical-align:top;">Abstract</td>
              <td style="padding:8px 0;color:#333;">{paper.get('abstract', '')}</td>
            </tr>
            """
            if paper.get("abstract")
            else ""
        )

        return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#f5f5f5; margin:0; padding:0; }}
    .container {{ max-width:640px; margin:30px auto; background:#fff;
                  border-radius:8px; overflow:hidden;
                  box-shadow:0 2px 8px rgba(0,0,0,.12); }}
    .header {{ background:#d32f2f; color:#fff; padding:24px 32px; }}
    .header h1 {{ margin:0; font-size:20px; letter-spacing:.5px; }}
    .header p  {{ margin:4px 0 0; font-size:13px; opacity:.85; }}
    .body   {{ padding:28px 32px; }}
    .badge  {{ display:inline-block; background:#e3f2fd; color:#1565c0;
               padding:4px 10px; border-radius:12px; font-size:12px;
               font-weight:600; margin-bottom:16px; }}
    table   {{ width:100%; border-collapse:collapse; }}
    td      {{ padding:8px 0; border-bottom:1px solid #f0f0f0;
               font-size:14px; vertical-align:top; }}
    td:first-child {{ color:#555; font-weight:600; width:140px; }}
    td:last-child  {{ color:#333; }}
    .cta    {{ display:block; margin:24px 0 0; padding:12px 24px;
               background:#d32f2f; color:#fff; text-align:center;
               text-decoration:none; border-radius:6px;
               font-weight:600; font-size:15px; }}
    .footer {{ background:#fafafa; border-top:1px solid #eee;
               padding:14px 32px; font-size:12px; color:#999;
               text-align:center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🔬 New Research Paper Found</h1>
      <p>Elsevier Paper Alert Agent</p>
    </div>
    <div class="body">
      <span class="badge">Matched keyword: {paper.get('keywords', '')}</span>
      <table>
        <tr>
          <td>Title</td>
          <td><strong>{paper.get('title', 'N/A')}</strong></td>
        </tr>
        <tr>
          <td>Authors</td>
          <td>{paper.get('authors', 'N/A')}</td>
        </tr>
        <tr>
          <td>Journal</td>
          <td>{paper.get('journal', 'N/A')}</td>
        </tr>
        <tr>
          <td>Published&nbsp;Date</td>
          <td>{paper.get('published', 'N/A')}</td>
        </tr>
        <tr>
          <td>DOI</td>
          <td><a href="https://doi.org/{doi}" style="color:#1565c0;">{doi or 'N/A'}</a></td>
        </tr>
        <tr>
          <td>Paper&nbsp;URL</td>
          <td><a href="{url}" style="color:#1565c0;">View Full Paper</a></td>
        </tr>
        {abstract_html}
      </table>
      <a class="cta" href="{url}">Read the Full Paper →</a>
    </div>
    <div class="footer">
      Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC &nbsp;|&nbsp;
      Elsevier Paper Alert Agent
    </div>
  </div>
</body>
</html>
"""

    def _send(self, recipient: str, subject: str, body_text: str, body_html: str):
        """Connect to SMTP and send the multipart email."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Elsevier Alert Agent <{self.sender}>"
        msg["To"] = recipient

        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(self.SMTP_HOST, self.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.sender, self.password)
            server.sendmail(self.sender, [recipient], msg.as_bytes())
