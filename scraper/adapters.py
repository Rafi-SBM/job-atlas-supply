from __future__ import annotations

import hashlib
import html
import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, unquote, urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from requests.adapters import HTTPAdapter

LOCAL = threading.local()
HOST_LOCK = threading.Lock()
HOST_HOLDS = {}
STOP_EVENT = threading.Event()


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(value)))).strip()


def date_value(value, milliseconds=False):
    if not value:
        return ""
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / (1000 if milliseconds else 1), timezone.utc).isoformat().replace("+00:00", "Z")
        microsoft = re.search(r"/Date\((\d+)", str(value))
        if microsoft:
            return date_value(int(microsoft.group(1)), True)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError, OSError, TypeError):
        return ""


def canonical_url(value):
    p = urlsplit(str(value or ""))
    if p.scheme not in ("https", "http") or not p.hostname:
        return ""
    params = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in {"source", "lever-source", "gh_src"}]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"), urlencode(params), ""))


def workplace(explicit="", location="", remote=None):
    s = str(explicit or "").lower()
    if "hybrid" in s:
        return "Hybrid"
    if remote is True or s == "remote":
        return "Remote"
    if s in {"onsite", "on-site", "on site", "office"}:
        return "On-site"
    if re.search(r"\bhybrid\b", location, re.I):
        return "Hybrid"
    if re.search(r"\bremote\b|work from home", location, re.I):
        return "Remote"
    return "Not specified"


def numeric(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def normalize(board, source_url, **values):
    platform, slug = board["platform"], board["board"]
    company_slug = slug.split("|")[0]
    company = text(values.pop("company", None) or board["company"])
    company_key = f"{platform}:{company_slug.lower()}"
    job_id = str(values.get("job_id") or hashlib.sha256(str(values.get("url", "")).encode()).hexdigest()[:24])
    # Workday publishes the same requisition to multiple external sites.
    key_board = company_slug if platform == "workday" else slug.lower()
    result = {
        "key": f"{platform}:{key_board}:{job_id}", "company": company,
        "company_key": company_key, "platform": platform, "board": slug,
        "job_id": job_id, "title": "", "location": "", "workplace": "Not specified",
        "department": "", "employment_type": "", "published_at": "", "updated_at": "",
        "salary_min": None, "salary_max": None, "salary_currency": "", "salary_interval": "",
        "url": "", "apply_url": "", "source_url": source_url, "description": "",
        "checked_at": utcnow(), "date_note": "", "salary_text": "",
    }
    result.update(values)
    for field in ("title", "location", "department", "employment_type", "description"):
        result[field] = text(result[field])
    result["url"] = canonical_url(result["url"])
    result["apply_url"] = canonical_url(result["apply_url"] or result["url"])
    return result if result["title"] and result["url"] else None


class FetchError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def session():
    if not hasattr(LOCAL, "session"):
        s = requests.Session()
        s.mount("https://", HTTPAdapter(pool_connections=16, pool_maxsize=2, max_retries=0))
        contact = os.environ.get("JOB_SCRAPER_CONTACT", "")
        s.headers.update({"User-Agent": f"JobAtlasLocal/1.0 (public career feeds; contact: {contact})", "Accept": "application/json, application/xml;q=0.9, text/html;q=0.8"})
        LOCAL.session = s
    return LOCAL.session


def request(url, payload=None):
    host = urlsplit(url).hostname
    for attempt in range(3):
        if STOP_EVENT.is_set():
            raise FetchError("Collection interrupted")
        while True:
            with HOST_LOCK:
                delay = HOST_HOLDS.get(host, 0) - time.monotonic()
            if delay <= 0:
                break
            if STOP_EVENT.wait(min(delay, 1)):
                raise FetchError("Collection interrupted")
        try:
            response = session().request("POST" if payload is not None else "GET", url, json=payload, timeout=(5, 18))
        except requests.RequestException as exc:
            if attempt == 0:
                time.sleep(1)
                continue
            raise FetchError(f"{type(exc).__name__}: {str(exc)[:180]}") from exc
        if response.status_code in (429, 502, 503, 504) and attempt < 2:
            header = response.headers.get("Retry-After", "")
            try:
                delay = float(header)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError):
                    delay = 2 ** (attempt + 1)
            if delay > 30:
                if response.status_code == 429:
                    with HOST_LOCK:
                        HOST_HOLDS[host] = max(HOST_HOLDS.get(host, 0), time.monotonic() + delay)
                raise FetchError(f"Rate limited; retry after {header}", response.status_code)
            if response.status_code == 429:
                with HOST_LOCK:
                    HOST_HOLDS[host] = max(HOST_HOLDS.get(host, 0), time.monotonic() + max(1, delay))
            time.sleep(max(1, delay))
            continue
        if response.status_code != 200:
            raise FetchError(f"HTTP {response.status_code}", response.status_code)
        return response
    raise FetchError("Retry budget exhausted")


def fetch_board(board):
    jobs = []
    result = {"board": board, "jobs": jobs, "status": "ok", "http_status": 200, "error": ""}
    try:
        for row in fetch_rows(board):
            if row is not None:
                jobs.append(row)
    except Exception as exc:
        status = getattr(exc, "status", None)
        result.update(status="partial" if jobs else "not_found" if status in (404, 410) else "error", http_status=status, error=str(exc)[:350])
    # Same posting occasionally appears twice in a response or repeated page.
    result["jobs"] = list({j["key"]: j for j in jobs}.values())
    return result


def fetch_rows(b):
    p, slug = b["platform"], b["board"]
    s = quote(slug, safe="-._")
    if p == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs"
        data = request(url).json()
        if not isinstance(data.get("jobs"), list):
            raise FetchError("Missing jobs array")
        for j in data["jobs"]:
            loc = (j.get("location") or {}).get("name", "")
            yield normalize(b, url, job_id=j["id"], title=j.get("title"), location=loc,
                workplace=workplace(location=loc), department="; ".join(d["name"] for d in j.get("departments", [])),
                updated_at=date_value(j.get("updated_at")), published_at=date_value(j.get("first_published")),
                url=j.get("absolute_url"), date_note="Greenhouse updated_at is a modification date, not a posting date.")
    elif p == "ashby":
        url = f"https://api.ashbyhq.com/posting-api/job-board/{s}?includeCompensation=true"
        data = request(url).json()
        if not isinstance(data.get("jobs"), list):
            raise FetchError("Missing jobs array")
        for j in data["jobs"]:
            if j.get("isListed") is False:
                continue
            comp = j.get("compensation") or {}
            tiers = comp.get("compensationTierSummary") or ""
            components = [c for c in comp.get("summaryComponents", []) if c.get("compensationType") == "Salary"]
            # Only expose a single structured range when currency and interval are unambiguous.
            salary = components[0] if len(components) == 1 else {}
            loc = j.get("location", "")
            yield normalize(b, url, job_id=j.get("id"), title=j.get("title"), location=loc,
                workplace=workplace(j.get("workplaceType"), loc, j.get("isRemote")), department=j.get("department"),
                employment_type=j.get("employmentType"), published_at=date_value(j.get("publishedAt")),
                url=j.get("jobUrl"), apply_url=j.get("applyUrl"), description=j.get("descriptionPlain") or j.get("descriptionHtml"),
                salary_min=numeric(salary.get("minValue")), salary_max=numeric(salary.get("maxValue")),
                salary_currency=salary.get("currencyCode", ""), salary_interval=salary.get("interval", ""), salary_text=text(tiers))
    elif p == "lever":
        url = f"https://api.lever.co/v0/postings/{s}?mode=json"
        try:
            response = request(url)
        except FetchError as exc:
            if exc.status != 404:
                raise
            url = f"https://api.eu.lever.co/v0/postings/{s}?mode=json"
            response = request(url)
        data = response.json()
        if not isinstance(data, list):
            raise FetchError("Expected postings array")
        for j in data:
            c = j.get("categories") or {}
            salary = j.get("salaryRange") or {}
            loc = c.get("location", "")
            yield normalize(b, url, job_id=j.get("id"), title=j.get("text"), location=loc,
                workplace=workplace(j.get("workplaceType"), loc), department=c.get("department") or c.get("team"),
                employment_type=c.get("commitment"), published_at=date_value(j.get("createdAt"), True),
                salary_min=numeric(salary.get("min")), salary_max=numeric(salary.get("max")),
                salary_currency=salary.get("currency", ""), salary_interval=salary.get("interval", ""),
                url=j.get("hostedUrl"), apply_url=j.get("applyUrl"), description=j.get("descriptionPlain"))
    elif p == "bamboohr":
        url = f"https://{s}.bamboohr.com/careers/list"
        data = request(url).json()
        if not isinstance(data.get("result"), list):
            raise FetchError("Missing careers result array")
        for j in data["result"]:
            loc = j.get("location") or {}
            loc = ", ".join(str(loc[k]) for k in ("city", "state", "country") if loc.get(k)) if isinstance(loc, dict) else str(loc)
            dep = j.get("department") or ""
            yield normalize(b, url, job_id=j.get("id"), title=j.get("jobOpeningName"), location=loc,
                department=dep.get("label", "") if isinstance(dep, dict) else dep,
                workplace=workplace(location=loc), employment_type=j.get("employmentStatusLabel"),
                url=f"https://{s}.bamboohr.com/careers/{j['id']}")
    elif p == "workday":
        company, wd, site = slug.split("|")
        base = f"https://{company}.{wd}.myworkdayjobs.com"
        url = f"{base}/wday/cxs/{company}/{quote(site, safe='')}/jobs"
        offset, expected, seen = 0, None, set()
        while True:
            data = request(url, {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""}).json()
            if not isinstance(data.get("jobPostings"), list) or not isinstance(data.get("total"), int):
                raise FetchError("Missing Workday postings/total")
            if expected is None:
                expected = data["total"]
            elif data["total"] != expected:
                raise FetchError("Workday total changed during pagination; partial board")
            rows = data["jobPostings"]
            if not rows:
                if offset < expected:
                    raise FetchError(f"Pagination stopped at {offset}/{expected}")
                break
            signature = tuple(j.get("externalPath") for j in rows)
            if signature in seen:
                raise FetchError("Repeated Workday page; partial board")
            seen.add(signature)
            for j in rows:
                path = j.get("externalPath", "")
                jid = path.rsplit("/", 1)[-1]
                req_id = (j.get("bulletFields") or [jid])[0]
                loc = j.get("locationsText", "")
                # Relative dates such as 30+ days are not exact posting dates.
                yield normalize(b, url, job_id=req_id, title=j.get("title"), location=loc,
                    workplace=workplace(location=loc), url=f"{base}/{quote(site, safe='')}{path}",
                    date_note=f"Workday reports: {j.get('postedOn', 'date unavailable')}")
            offset += len(rows)
            if offset >= expected:
                break
            time.sleep(0.15)
    elif p == "paylocity":
        url = f"https://recruiting.paylocity.com/recruiting/jobs/All/{s}/"
        page = request(url).text
        match = re.search(r"window\.pageData\s*=\s*(\{.*?\})\s*;\s*</script>", page, re.S)
        if not match:
            raise FetchError("Paylocity pageData missing; board not assumed empty")
        data = json.loads(match.group(1))
        if not isinstance(data.get("Jobs"), list):
            raise FetchError("Paylocity Jobs array missing")
        for j in data["Jobs"]:
            loc = j.get("JobLocation") or {}
            loc = ", ".join(str(loc[k]) for k in ("City", "State", "Country") if loc.get(k)) or j.get("LocationName", "")
            yield normalize(b, url, job_id=j.get("JobId"), title=j.get("JobTitle"), location=loc,
                workplace=workplace(location=loc, remote=j.get("IsRemote")), department=j.get("HiringDepartment"),
                published_at=date_value(j.get("PublishedDate")),
                url=f"https://recruiting.paylocity.com/recruiting/Jobs/Details/{j['JobId']}")
    elif p == "icims":
        url = f"https://careers-{s}.icims.com/sitemap.xml"
        pending, visited = [url], set()
        while pending:
            current = pending.pop(0)
            if current in visited:
                continue
            visited.add(current)
            root = ET.fromstring(request(current).content)
            if root.tag.rsplit("}", 1)[-1] not in {"urlset", "sitemapindex"}:
                raise FetchError("Unexpected sitemap format")
            if root.tag.endswith("sitemapindex"):
                for e in root.findall("{*}sitemap/{*}loc"):
                    child = (e.text or "").strip()
                    if urlsplit(child).hostname == urlsplit(url).hostname:
                        pending.append(child)
                continue
            for e in root.findall("{*}url"):
                job_url = (e.findtext("{*}loc") or "").strip()
                match = re.search(r"/jobs/(\d+)/([^/]+)/job", job_url)
                if not match:
                    continue
                yield normalize(b, current, job_id=match[1], title=unquote(match[2]).replace("-", " "),
                    updated_at=date_value(e.findtext("{*}lastmod")), url=job_url,
                    date_note="Listed in current employer sitemap. Title derived from URL; location unavailable. Detail page not individually verified.")
    elif p == "workable":
        url = f"https://apply.workable.com/api/v1/widget/accounts/{s}?details=true"
        data = request(url).json()
        if not isinstance(data.get("jobs"), list):
            raise FetchError("Workable jobs missing")
        for j in data["jobs"]:
            loc = j.get("location", "")
            if isinstance(loc, dict):
                loc = ", ".join(str(loc.get(k)) for k in ("city", "region", "country") if loc.get(k))
            yield normalize(b, url, job_id=j.get("shortcode") or j.get("id"), title=j.get("title"), location=loc,
                workplace=workplace(location=loc, remote=j.get("telecommuting")), department=j.get("department"),
                published_at=date_value(j.get("published_on")), url=j.get("url") or f"https://apply.workable.com/{s}/j/{j.get('shortcode')}/")
    elif p == "recruitee":
        url = f"https://{s}.recruitee.com/api/offers/"
        data = request(url).json()
        if not isinstance(data.get("offers"), list):
            raise FetchError("Recruitee offers missing")
        for j in data["offers"]:
            loc = j.get("location", "")
            yield normalize(b, url, job_id=j.get("id"), title=j.get("title"), location=loc,
                workplace=workplace(location=loc, remote=j.get("remote")), department=j.get("department"),
                employment_type=j.get("employment_type_code"), published_at=date_value(j.get("published_at")),
                url=j.get("careers_url"), description=j.get("description"))
    elif p == "smartrecruiters":
        url = f"https://api.smartrecruiters.com/v1/companies/{s}/postings"
        offset, total = 0, None
        while total is None or offset < total:
            data = request(f"{url}?limit=100&offset={offset}").json()
            if not isinstance(data.get("content"), list):
                raise FetchError("SmartRecruiters content missing")
            total = int(data.get("totalFound", 0))
            if not data["content"] and offset < total:
                raise FetchError("SmartRecruiters pagination truncated")
            for j in data["content"]:
                location = j.get("location") or {}
                loc = ", ".join(str(location[k]) for k in ("city", "region", "country") if location.get(k))
                yield normalize(b, url, job_id=j.get("id"), title=j.get("name"), location=loc,
                    workplace=workplace(location=loc, remote=location.get("remote")),
                    department=(j.get("department") or {}).get("label"),
                    employment_type=(j.get("typeOfEmployment") or {}).get("label"),
                    published_at=date_value(j.get("releasedDate")), url=f"https://jobs.smartrecruiters.com/{s}/{j['id']}")
            offset += len(data["content"])
            if not data["content"]:
                break
    elif p == "personio":
        url = f"https://{s}.jobs.personio.de/xml"
        root = ET.fromstring(request(url).content)
        if root.tag != "workzag-jobs":
            raise FetchError("Personio feed missing")
        for j in root.findall("position"):
            jid = j.findtext("id")
            loc = j.findtext("office", "")
            yield normalize(b, url, job_id=jid, title=j.findtext("name"), location=loc,
                department=j.findtext("department"), employment_type=j.findtext("employmentType"),
                workplace=workplace(location=loc), published_at=date_value(j.findtext("createdAt")),
                url=f"https://{s}.jobs.personio.de/job/{jid}")
    elif p == "breezy":
        url = f"https://{s}.breezy.hr/json"
        data = request(url).json()
        if not isinstance(data, list):
            raise FetchError("Breezy positions missing")
        for j in data:
            loc = (j.get("location") or {}).get("name", "")
            yield normalize(b, url, job_id=j.get("id"), title=j.get("name"), location=loc,
                workplace=workplace(location=loc, remote=(j.get("location") or {}).get("is_remote")),
                department=j.get("department"), employment_type=(j.get("type") or {}).get("name"),
                url=j.get("url"), published_at=date_value(j.get("published_date")))
    else:
        raise FetchError(f"Unsupported platform {p}")
