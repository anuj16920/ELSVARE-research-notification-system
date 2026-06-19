"""
main.py - Entry point for the Elsevier Paper Alert Agent
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env before importing anything that reads env vars ────────────────────
load_dotenv()

from database import init_db, paper_exists, insert_paper, insert_notification, \
    mark_notification_sent, mark_notification_failed, get_pending_notifications, get_stats
from elsevier_client import ElsevierClient
from email_service import EmailService
from scheduler import build_scheduler

# ── Logging setup ──────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "agent.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY", "")
EMAIL_ADDRESS    = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
RECEIVER_EMAIL   = os.getenv("RECEIVER_EMAIL", "")
KEYWORDS_FILE    = Path(os.getenv("KEYWORDS_FILE", "keywords.json"))


def load_keywords() -> list[str]:
    """Load keyword list from keywords.json."""
    if not KEYWORDS_FILE.exists():
        logger.error("keywords.json not found at %s", KEYWORDS_FILE)
        sys.exit(1)
    with open(KEYWORDS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    keywords = data.get("keywords", [])
    if not keywords:
        logger.error("No keywords found in %s", KEYWORDS_FILE)
        sys.exit(1)
    logger.info("Loaded %d keywords: %s", len(keywords), keywords)
    return keywords


def validate_config():
    """Fail fast with clear messages if required env vars are missing."""
    missing = []
    if not ELSEVIER_API_KEY:
        missing.append("ELSEVIER_API_KEY")
    if not EMAIL_ADDRESS:
        missing.append("EMAIL_ADDRESS")
    if not EMAIL_APP_PASSWORD:
        missing.append("EMAIL_APP_PASSWORD")
    if not RECEIVER_EMAIL:
        missing.append("RECEIVER_EMAIL")
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        logger.error("Copy .env.example → .env and fill in the values.")
        sys.exit(1)


def monitoring_job():
    """
    Core job executed every 30 minutes:
    1. Fetch new papers from Elsevier matching keywords
    2. Store new papers in SQLite
    3. Send email alerts
    """
    logger.info("── Monitoring job started ──")
    keywords  = load_keywords()
    client    = ElsevierClient(ELSEVIER_API_KEY)
    emailer   = EmailService(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)

    # ── 1. Fetch papers ──────────────────────────────────────────────────────
    try:
        papers = client.search_new_papers(keywords)
    except Exception as exc:
        logger.error("Failed to fetch papers from Elsevier: %s", exc)
        return

    new_count = 0
    for paper in papers:
        doi = paper.get("doi", "")

        # ── 2. Deduplication ────────────────────────────────────────────────
        if doi and paper_exists(doi):
            logger.debug("Skipping already-seen DOI: %s", doi)
            continue

        # ── 3. Persist ───────────────────────────────────────────────────────
        try:
            paper_id = insert_paper(paper)
            notif_id = insert_notification(paper_id, RECEIVER_EMAIL)
        except Exception as exc:
            logger.error("DB error for DOI %s: %s", doi, exc)
            continue

        # ── 4. Send email immediately ────────────────────────────────────────
        try:
            emailer.send_paper_alert(paper, RECEIVER_EMAIL)
            mark_notification_sent(notif_id)
            new_count += 1
            logger.info(
                "✔ Alert sent — %s | %s", paper.get("title", "")[:70], doi
            )
        except Exception as exc:
            mark_notification_failed(notif_id, str(exc))
            logger.error("Email failed for DOI %s: %s", doi, exc)

    # ── 5. Retry any pending notifications from previous failed attempts ─────
    _retry_pending(emailer)

    stats = get_stats()
    logger.info(
        "── Job done: %d new paper(s) this run | DB: %s ──",
        new_count, stats
    )


def _retry_pending(emailer: EmailService):
    """Attempt to send any previously failed notification emails."""
    pending = get_pending_notifications()
    if not pending:
        return
    logger.info("Retrying %d pending notification(s) …", len(pending))
    for row in pending:
        paper = dict(row)
        notif_id = paper.pop("notification_id")
        try:
            emailer.send_paper_alert(paper, paper["recipient"])
            mark_notification_sent(notif_id)
            logger.info("Retry succeeded for DOI: %s", paper.get("doi"))
        except Exception as exc:
            mark_notification_failed(notif_id, str(exc))
            logger.warning("Retry failed for DOI %s: %s", paper.get("doi"), exc)


def main():
    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║    Elsevier Paper Alert Agent v1.0       ║")
    logger.info("╚══════════════════════════════════════════╝")

    validate_config()
    init_db()

    # Run once immediately so you see results without waiting 30 minutes
    logger.info("Running initial check …")
    monitoring_job()

    # Then schedule every 30 minutes
    logger.info("Starting scheduler (every 30 minutes) …")
    scheduler = build_scheduler(monitoring_job, blocking=True)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Agent stopped by user.")


if __name__ == "__main__":
    main()
