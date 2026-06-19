"""
database.py - SQLite database management for Elsevier Paper Alert Agent
"""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("papers.db")


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database tables."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS papers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doi         TEXT    NOT NULL UNIQUE,
                title       TEXT    NOT NULL,
                authors     TEXT,
                journal     TEXT,
                published   TEXT,
                abstract    TEXT,
                url         TEXT,
                keywords    TEXT,
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id        INTEGER NOT NULL REFERENCES papers(id),
                email_sent      INTEGER NOT NULL DEFAULT 0,
                sent_at         TEXT,
                recipient       TEXT,
                error_message   TEXT,
                created_at      TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_papers_doi     ON papers(doi);
            CREATE INDEX IF NOT EXISTS idx_papers_created ON papers(created_at);
            CREATE INDEX IF NOT EXISTS idx_notif_paper    ON notifications(paper_id);
            CREATE INDEX IF NOT EXISTS idx_notif_sent     ON notifications(email_sent);
        """)
    logger.info("Database initialized at %s", DB_PATH)


def paper_exists(doi: str) -> bool:
    """Return True if a paper with this DOI is already in the database."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM papers WHERE doi = ?", (doi,)
        ).fetchone()
        return row is not None


def insert_paper(paper: dict) -> int:
    """Insert a new paper and return its row id."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO papers
                (doi, title, authors, journal, published, abstract, url, keywords, created_at)
            VALUES
                (:doi, :title, :authors, :journal, :published, :abstract, :url, :keywords, :created_at)
            """,
            {
                "doi":        paper.get("doi", ""),
                "title":      paper.get("title", ""),
                "authors":    paper.get("authors", ""),
                "journal":    paper.get("journal", ""),
                "published":  paper.get("published", ""),
                "abstract":   paper.get("abstract", ""),
                "url":        paper.get("url", ""),
                "keywords":   paper.get("keywords", ""),
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        paper_id = cur.lastrowid
        logger.debug("Inserted paper id=%d doi=%s", paper_id, paper.get("doi"))
        return paper_id


def insert_notification(paper_id: int, recipient: str) -> int:
    """Create a notification record (email_sent=0) and return its id."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO notifications (paper_id, email_sent, recipient, created_at)
            VALUES (?, 0, ?, ?)
            """,
            (paper_id, recipient, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def mark_notification_sent(notification_id: int):
    """Mark a notification as sent."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE notifications
            SET email_sent = 1, sent_at = ?
            WHERE id = ?
            """,
            (datetime.utcnow().isoformat(), notification_id),
        )


def mark_notification_failed(notification_id: int, error: str):
    """Record an email send failure."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE notifications
            SET error_message = ?
            WHERE id = ?
            """,
            (error, notification_id),
        )


def get_pending_notifications() -> list[sqlite3.Row]:
    """Return all notification rows where email has not been sent."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT n.id         AS notification_id,
                   p.doi        AS doi,
                   p.title      AS title,
                   p.authors    AS authors,
                   p.journal    AS journal,
                   p.published  AS published,
                   p.url        AS url,
                   p.keywords   AS keywords,
                   n.recipient  AS recipient
            FROM   notifications n
            JOIN   papers        p ON p.id = n.paper_id
            WHERE  n.email_sent = 0
            ORDER  BY n.created_at
            """
        ).fetchall()


def get_stats() -> dict:
    """Return quick stats for logging."""
    with get_connection() as conn:
        total_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        sent = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE email_sent = 1"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE email_sent = 0"
        ).fetchone()[0]
    return {"total_papers": total_papers, "emails_sent": sent, "emails_pending": pending}
