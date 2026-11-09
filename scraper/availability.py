"""Positive, job-specific evidence that an application is currently open."""
from __future__ import annotations
import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit
from lxml import html as lhtml


GENERAL = re.compile(
    r"general (?:employment |job )?(?:application|interest|inquir)|open application|"
    r"unsolicited|speculative application|expressions? of interest|"
    r"talent (?:pool|community|network|pipeline)|future (?:career |job |employment )?opportunit|"
    r"future openings|future consideration|evergreen|resume (?:bank|pool)|"
    r"not (?:currently )?hiring|no (?:current |open )?(?:positions|openings)|"
    r"join (?:our|the) (?:talent|team|network)|"
    r"^(?:test|dummy|sample|demo) (?:job|posting|position|requisition)\b|"
    r"position(?:s)? not shown|job(?:s)? not listed|"
    r"(?:don.t|do not|didn.t|did not|can.t|cannot) (?:see|find)\b|"
    r"submit (?:your|a) (?:resume|cv)|send (?:us )?your (?:resume|cv)|"
    r"register (?:your )?interest|general (?:resume|cv|submission|applicants?|candidates?|consideration|opportunit(?:y|ies)|positions?|openings|career|insurance opportunities)|"
    r"general internship inquiry|general .{0,35}(?:job|career) application|spontaneous application|"
    r"(?:resume|cv) (?:drop|submission|upload|bank)|drop (?:a |your )?(?:resume|cv)|"
    r"^future\b|^pipeline[\])]|^(?:test|demo|sample|placeholder|dummy)[!?. ]*$|"
    r"(?:candidate|resume) pool(?:[\s-]+\d{4}.*)?[!?. ]*$|"
    r"apply.{0,30}future (?:jobs?|roles?|positions|opportunities|openings)|"
    r"^interested in (?:joining|working)\b|^open roles\b|^career opportunities\b|"
    r"hiring event|career fair|job fair|recruit(?:ing|ment) event|"
    r"do not apply|for testing only|not an? (?:active|current|live) (?:job|vacancy|position)|"
    r"^(?:join us|work with us|apply (?:here|now)|open (?:positions?|roles?|opportunities)|"
    r"all (?:positions?|roles?|opportunities)|careers?(?: at .+)?|opportunities(?: at .+)?)[!?. ]*$", re.I)


def non_vacancy(title):
    return bool(GENERAL.search(re.sub(r"^[\W_]+", "", title or "")))


def expired(value, now=None):
    if not value:
        return False
    now = now or datetime.now(timezone.utc)
    try:
        if isinstance(value, dict):
            value = value.get("date") or value.get("deadline") or ""
        text = str(value)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return datetime.fromisoformat(text).date() < now.date()
        date = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return date.replace(tzinfo=date.tzinfo or timezone.utc) < now
    except (ValueError, TypeError):
        # An unreadable, supplied deadline cannot pass a strict verification.
        return True


def target(row):
    p, b, j = row["platform"], quote(row["board"], safe="-._"), quote(row["job_id"], safe="-._")
    if p == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{b}/jobs/{j}?questions=true"
    if p == "bamboohr":
        return f"https://{b}.bamboohr.com/careers/{j}/detail"
    if p == "workday":
        tenant, wd, site = row["board"].split("|")
        path = row["url"].split("/job/", 1)[1]
        return f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/job/{path}"
    if p == "lever":
        return row["apply_url"].split("?", 1)[0].rstrip("/").removesuffix("/apply") + "/apply"
    if p == "ashby":
        return f"https://jobs.ashbyhq.com/{b}/{j}/application"
    if p == "breezy":
        return row["url"].rstrip("/") + "/apply"
    if p == "paylocity":
        return f"https://recruiting.paylocity.com/recruiting/Jobs/Apply/{j}"
    return row["apply_url"] or row["url"]


def country_location(value):
    if not isinstance(value, dict):
        return str(value or "")
    return ", ".join(str(value[k]) for k in ("city", "state", "addressCountry", "country") if value.get(k))


def evidence(row, body, final_url):
    """Return status/reason plus current title/location. HTTP success alone fails."""
    p = row["platform"]
    title, location, reason = "", "", ""
    if p == "greenhouse":
        d = json.loads(body)
        if str(d.get("id")) != row["job_id"]:
            return "unconfirmed", "Job identifier mismatch", {}
        if not d.get("internal_job_id"):
            return "excluded_general", "Prospect post without a job requisition", {}
        if expired(d.get("application_deadline")):
            return "closed", "Application deadline passed or cannot be confirmed", {}
        fields = {f.get("name") for q in d.get("questions", []) for f in q.get("fields", [])}
        if not {"first_name", "last_name", "email"}.issubset(fields):
            return "unconfirmed", "No current applicant identity fields returned", {}
        title, location = d.get("title", ""), (d.get("location") or {}).get("name", "")
        reason = "Exact live job ID; job requisition present; first-name, last-name and email application fields returned; deadline checked"
    elif p == "bamboohr":
        d = json.loads(body).get("result") or {}
        j, form = d.get("jobOpening") or {}, d.get("formFields") or {}
        if str(j.get("jobOpeningStatus", "")).casefold() != "open":
            return "closed", "Job opening status is not Open", {}
        share = j.get("jobOpeningShareUrl", "").rstrip("/")
        if not share.endswith("/careers/" + row["job_id"]):
            return "unconfirmed", "Job identifier mismatch", {}
        if not {"firstName", "lastName", "email"}.issubset(form):
            return "unconfirmed", "No application form fields returned", {}
        title, location = j.get("jobOpeningName", ""), country_location(j.get("location"))
        reason = "Exact job URL; jobOpeningStatus=Open; applicant name and email form fields returned"
    elif p == "workday":
        j = json.loads(body).get("jobPostingInfo") or {}
        if j.get("canApply") is not True or j.get("posted") is not True:
            return "closed", "Workday canApply or posted is not true", {}
        if j.get("jobReqId") != row["job_id"]:
            return "unconfirmed", "Requisition identifier mismatch", {}
        country = (j.get("country") or {}).get("descriptor", "")
        title = j.get("title", "")
        location = ", ".join(v for v in [j.get("location", ""), country] if v)
        reason = "Exact requisition ID; Workday canApply=true and posted=true"
    elif p == "ashby":
        match = re.search(r"window\.__appData\s*=\s*", body)
        if not match:
            return "unconfirmed", "No live application-page posting state", {}
        d = json.JSONDecoder().raw_decode(body[match.end():])[0]
        j = d.get("posting") or {}
        if not j or j.get("isListed") is not True:
            return "closed", "Application page has no listed posting", {}
        if j.get("id") != row["job_id"] or row["job_id"] not in final_url:
            return "unconfirmed", "Application page identifier mismatch", {}
        if expired(j.get("applicationDeadline")):
            return "closed", "Application deadline passed or cannot be confirmed", {}
        if d.get("maintenanceMode"):
            return "unconfirmed", "Application site is in maintenance", {}
        callout = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", j.get("applicationLimitCalloutHtml") or ""))
        if re.search(r"(?:no longer|not currently|not) accepting (?:new )?applications|applications (?:are |have been )?closed|position (?:is )?(?:closed|filled)", callout, re.I):
            return "closed", "Application page explicitly says applications are closed", {}
        title = j.get("title", "")
        location = "; ".join([j.get("locationName", "")] + (j.get("secondaryLocationNames") or []))
        reason = "Exact posting loaded at its live application URL; isListed=true; deadline checked; no application-closure notice"
    else:
        doc = lhtml.fromstring(body)
        forms = doc.xpath('//form[@id="application-form" or @id="applicationForm"]')
        if not forms or row["job_id"] not in final_url:
            return "unconfirmed", "No job-specific application form confirmed", {}
        fields = {v.casefold() for f in forms for v in f.xpath('.//input/@name')}
        if "email" not in fields or not fields.intersection({"name", "firstname", "first_name"}):
            return "unconfirmed", "No applicant name and email form inputs confirmed", {}
        titles = doc.xpath('//h2[not(ancestor::form)]/text()')
        title = titles[0].strip() if titles else ""
        locations = doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " location ")]/text()')
        location = "; ".join(v.strip() for v in locations if v.strip())
        reason = "Exact job ID in live application URL; application form with applicant name and email inputs present"
    title = re.sub(r"\s+", " ", html.unescape(title)).strip()
    if not title or non_vacancy(title):
        return "excluded_general", "Generic, future-interest or non-vacancy posting", {}
    if not location:
        return "unconfirmed", "Current US location not confirmed on the application response", {}
    return "open", reason, {"title": title, "location": location}
