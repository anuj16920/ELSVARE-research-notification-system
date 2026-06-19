"""
elsevier_client.py - Elsevier ScienceDirect / Scopus API client
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
SCIDIR_SEARCH_URL = "https://api.elsevier.com/content/search/sciencedirect"

# How far back to look on each poll (slightly longer than interval to avoid gaps)
LOOKBACK_MINUTES = 35


class ElsevierClient:
    """Thin wrapper around the Elsevier Scopus Search API."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("ELSEVIER_API_KEY is required")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-ELS-APIKey": api_key,
                "Accept": "application/json",
                "User-Agent": "ElsevierAlertAgent/1.0",
            }
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search_new_papers(self, keywords: list[str]) -> list[dict]:
        """
        Search Scopus for recently published papers matching any of the
        provided keywords.  Returns a deduplicated list of paper dicts.
        """
        last_year = (datetime.now(timezone.utc).year - 1)

        seen_dois: set[str] = set()
        papers: list[dict] = []

        for keyword in keywords:
            try:
                results = self._search_keyword(keyword, last_year)
                for paper in results:
                    doi = paper.get("doi", "")
                    if doi and doi not in seen_dois:
                        seen_dois.add(doi)
                        papers.append(paper)
                    elif not doi:
                        # Keep papers without DOI (use title as dedup key)
                        title_key = paper.get("title", "").lower()[:80]
                        if title_key not in seen_dois:
                            seen_dois.add(title_key)
                            papers.append(paper)
            except Exception as exc:
                logger.error("Error searching keyword '%s': %s", keyword, exc)
            # Be polite to the API
            time.sleep(0.5)

        logger.info("Found %d unique new papers across %d keywords", len(papers), len(keywords))
        return papers

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _search_keyword(self, keyword: str, since_year: int) -> list[dict]:
        """Query Scopus for one keyword and return parsed paper list."""
        # LOAD-DATE requires institutional API access; PUBYEAR is available on all keys.
        # Sorting by newest cover date ensures fresh papers surface first.
        # DB dedup (DOI) prevents re-alerting on papers already seen.
        query = f'TITLE-ABS-KEY("{keyword}") AND PUBYEAR > {since_year}'

        params = {
            "query": query,
            "count": 25,
            "start": 0,
            "field": "dc:title,dc:creator,prism:publicationName,prism:doi,"
                     "prism:coverDate,dc:description,prism:url,authkeywords",
            "sort": "-coverdate",
        }

        resp = self._get(SCOPUS_SEARCH_URL, params)
        if resp is None:
            return []

        entries = (
            resp.get("search-results", {})
            .get("entry", [])
        )

        papers = []
        for entry in entries:
            # Skip error entries (Scopus returns {"error":"..."} on quota exceeded)
            if "error" in entry:
                logger.warning("Scopus entry error: %s", entry["error"])
                continue
            papers.append(self._parse_entry(entry, keyword))

        return papers

    def _parse_entry(self, entry: dict, matched_keyword: str) -> dict:
        """Normalise a Scopus search entry into our internal paper dict."""
        doi = entry.get("prism:doi", "")
        url = (
            f"https://doi.org/{doi}"
            if doi
            else entry.get("prism:url", "")
        )

        # Authors: Scopus often returns only the first author in basic fields
        authors_raw = entry.get("dc:creator", "")
        if isinstance(authors_raw, list):
            authors = ", ".join(authors_raw)
        else:
            authors = authors_raw or "N/A"

        # Keywords from the paper itself
        paper_keywords = entry.get("authkeywords", "") or ""
        if isinstance(paper_keywords, list):
            paper_keywords = ", ".join(paper_keywords)

        return {
            "doi":       doi.strip(),
            "title":     entry.get("dc:title", "Untitled").strip(),
            "authors":   authors.strip(),
            "journal":   entry.get("prism:publicationName", "N/A").strip(),
            "published": entry.get("prism:coverDate", "N/A"),
            "abstract":  (entry.get("dc:description", "") or "").strip(),
            "url":       url.strip(),
            "keywords":  matched_keyword,         # keyword that matched
            "paper_keywords": paper_keywords,     # keywords on the paper itself
        }

    def _get(self, url: str, params: dict) -> Optional[dict]:
        """HTTP GET with basic retry logic."""
        for attempt in range(1, 4):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    logger.warning("Rate limited; sleeping %ds", retry_after)
                    time.sleep(retry_after)
                    continue
                if resp.status_code == 401:
                    logger.error("Elsevier API authentication failed — check ELSEVIER_API_KEY")
                    return None
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                logger.warning("Attempt %d/%d failed: %s", attempt, 3, exc)
                if attempt < 3:
                    time.sleep(5 * attempt)
        return None
