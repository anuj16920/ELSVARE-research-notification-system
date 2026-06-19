# 🔬 Elsevier Paper Alert Agent.


An autonomous Python agent that monitors the **Elsevier Scopus API** every 30 minutes and sends you an **email alert** whenever a new research paper matching your keywords is published.

---

## Features

- ✅ Monitors Elsevier Scopus every **30 minutes**
- ✅ Keyword-based paper matching (any keyword triggers an alert)
- ✅ **Duplicate prevention** via SQLite DOI tracking
- ✅ **Immediate email** on new paper discovery
- ✅ Beautiful **HTML + plain-text** email format
- ✅ Retry queue for failed email sends
- ✅ Structured logging to `logs/agent.log`
- ✅ Docker-ready with `docker compose up -d`

---

## Folder Structure

```
elsevier-alert-agent/
├── main.py              # Entry point — validation, job orchestration, scheduler
├── scheduler.py         # APScheduler 30-minute interval setup
├── elsevier_client.py   # Scopus Search API wrapper with retry logic
├── email_service.py     # SMTP email sender (HTML + plain text)
├── database.py          # SQLite: papers + notifications tables
├── keywords.json        # Your search keywords
├── requirements.txt     # Python dependencies
├── Dockerfile           # Production Docker image
├── docker-compose.yml   # One-command deployment
├── .env.example         # Environment variable template
├── logs/                # Log files (auto-created)
└── README.md
```

---

## Quick Start

### 1. Configure secrets

```bash
cp .env.example .env
```

Edit `.env`:

```env
ELSEVIER_API_KEY=your_key_here          # https://dev.elsevier.com/
EMAIL_ADDRESS=you@gmail.com             # Gmail sender
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx  # https://myaccount.google.com/apppasswords
RECEIVER_EMAIL=alerts@example.com       # Where to receive alerts
```

### 2. Set your keywords

Edit `keywords.json`:

```json
{
  "keywords": [
    "machine learning",
    "transformer architecture",
    "reinforcement learning",
    "large language models",
    "computer vision"
  ]
}
```

---

## Running

### Option A — Docker (recommended)

```bash
docker compose up -d          # Start in background
docker compose logs -f        # Follow logs
docker compose down           # Stop
```

### Option B — Python directly

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Email Alert Format

**Subject:** `🔬 NEW RESEARCH PAPER FOUND`

```
Title:          Deep Learning for Medical Image Analysis
Authors:        Zhang, W.; Li, H.; Chen, M.
Journal:        Pattern Recognition
Published Date: 2025-06-15
DOI:            10.1016/j.patcog.2025.06.001
Keywords:       deep learning
Paper URL:      https://doi.org/10.1016/j.patcog.2025.06.001
```

---

## Database Schema

### `papers`
| Column       | Type    | Description                    |
|--------------|---------|--------------------------------|
| id           | INTEGER | Primary key                    |
| doi          | TEXT    | Unique DOI (deduplication key) |
| title        | TEXT    | Paper title                    |
| authors      | TEXT    | Author list                    |
| journal      | TEXT    | Publication name               |
| published    | TEXT    | Cover date                     |
| abstract     | TEXT    | Abstract text                  |
| url          | TEXT    | Paper URL                      |
| keywords     | TEXT    | Matched keyword                |
| created_at   | TEXT    | UTC insert timestamp           |

### `notifications`
| Column        | Type    | Description              |
|---------------|---------|--------------------------|
| id            | INTEGER | Primary key              |
| paper_id      | INTEGER | FK → papers.id           |
| email_sent    | INTEGER | 0=pending, 1=sent        |
| sent_at       | TEXT    | UTC send timestamp       |
| recipient     | TEXT    | Recipient email          |
| error_message | TEXT    | Last error (if any)      |
| created_at    | TEXT    | UTC insert timestamp     |

---

## Getting an Elsevier API Key

1. Visit [https://dev.elsevier.com/](https://dev.elsevier.com/)
2. Click **"I want an API key"**
3. Register (free)
4. Copy the key into your `.env`

> **Note:** Free Elsevier API keys have a rate limit of ~25 requests/second and access to Scopus abstract/metadata. Full-text access requires institutional subscriptions.

---

## Getting a Gmail App Password

1. Enable [2-Step Verification](https://myaccount.google.com/security) on your Google account
2. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Select **"Mail"** + **"Other"**, name it "Elsevier Agent"
4. Copy the 16-character password into `EMAIL_APP_PASSWORD` in `.env`

---

## Logs

Logs are written to both stdout and `logs/agent.log`:

```
2025-06-15 10:00:00 [INFO] __main__: ── Monitoring job started ──
2025-06-15 10:00:03 [INFO] elsevier_client: Found 3 unique new papers across 5 keywords
2025-06-15 10:00:05 [INFO] __main__: ✔ Alert sent — Deep Learning for Medical Imaging | 10.1016/...
2025-06-15 10:00:05 [INFO] __main__: ── Job done: 1 new paper(s) this run | DB: {...} ──
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Unauthorized` from Elsevier | Check `ELSEVIER_API_KEY` in `.env` |
| `SMTPAuthenticationError` | Use Gmail App Password, not your real password |
| No papers found | Broaden keywords; Elsevier free tier searches last 35 min of indexed papers |
| Duplicate alerts | DOI dedup is automatic; if you see dupes, the paper has no DOI — open an issue |
