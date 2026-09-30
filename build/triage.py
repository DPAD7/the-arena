"""A failed run on GitHub, read and named (Jose, Sep 30, 2026: "add a
   notification system so if that happens it sends you or the code something
   so it auto diagnoses and fixes").

   .github/workflows/watch.yml runs this whenever one of the board's
   workflows finishes in failure. It reads the failed job's log, names the
   cause, and does what the cause calls for:

     login      DraftKings' login has expired (dk_bets says LOGIN EXPIRED, or
                a 401 minting the token). Only Jose can mend that: an alert
                on his phone says so, once a day.
     transient  the network or a site was down (timeouts, resets, 5xx). A
                sweep is run again once; the rest run again on their own
                next wake. An alert, no issue.
     code       a traceback. An issue labeled "fault" is opened (or the open
                one for the same fault gets the new run), with the traceback,
                the script and the commit, and mend.yml sets Claude on it.
                An alert says what broke.
     unknown    anything else: an issue with the log's last lines, and an alert.

   Environment: GITHUB_TOKEN, GITHUB_REPOSITORY, RUN_ID, RUN_NAME,
   RUN_URL, HEAD_SHA, SITE (the board), ASK_SECRET (signs the alert).
"""
import json
import os
import re
import sys
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "DPAD7/the-arena")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
RUN_ID = os.environ.get("RUN_ID", "")
RUN_NAME = os.environ.get("RUN_NAME", "")
RUN_URL = os.environ.get("RUN_URL", "")
HEAD_SHA = os.environ.get("HEAD_SHA", "")[:7]
SITE = os.environ.get("SITE", "https://the-arenasports.pages.dev")
ASK = os.environ.get("ASK_SECRET", "")
API = "https://api.github.com"


class _Bare(urllib.request.HTTPRedirectHandler):
    """A log is handed over by a redirect to a signed store URL that refuses
       GitHub's own token: the redirect is followed without it."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return urllib.request.Request(newurl, method="GET")


OPEN = urllib.request.build_opener(_Bare).open


def gh(path, data=None, method=None):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode() if data is not None else None,
                                 method=method or ("POST" if data is not None else "GET"))
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with OPEN(req, timeout=60) as r:
        body = r.read()
        return json.loads(body) if body.strip().startswith(b"{") or body.strip().startswith(b"[") else body.decode("utf-8", "replace")


def logs_of(run):
    """The failed jobs' logs, timestamps off, secrets never in them (GitHub
       masks them), any cookie line dropped for good measure."""
    out = []
    jobs = gh("/repos/%s/actions/runs/%s/jobs" % (REPO, run)).get("jobs", [])
    for j in jobs:
        if j.get("conclusion") != "failure":
            continue
        try:
            text = gh("/repos/%s/actions/jobs/%s/logs" % (REPO, j["id"]))
        except Exception as e:
            text = "log unreadable: %s" % e
        lines = [re.sub(r"^\S+Z ", "", l) for l in str(text).splitlines()]
        # a line that carries a cookie's value is dropped; a line that only
        # speaks of cookies (dk_bets: "the cookies no longer mint a token") stays
        lines = [l for l in lines if not re.search(r"cookie\S*\s*[:=]\s*\S", l, re.I)]
        out.append((j.get("name") or "job", lines))
    return out


def name_it(lines):
    """The cause and the lines that say it."""
    text = "\n".join(lines)
    script = ""
    for l in lines:
        m = re.search(r"python3? (build/\S+\.py)", l)
        if m:
            script = m.group(1)
    if re.search(r"LOGIN EXPIRED|no longer mint a token|\b401\b.*token|token.*\b401\b", text):
        return "login", script, "DraftKings logged you out: export the login again; the bets pull waits for it."
    tb = None
    m = list(re.finditer(r"Traceback \(most recent call last\):", text))
    if m:
        start = m[-1].start()
        block = text[start:].split("\n")
        # the traceback runs to its last line, the error itself
        end = next((i for i, l in enumerate(block[1:], 1) if l and not l.startswith(" ") and not l.startswith("Traceback")), len(block) - 1)
        tb = "\n".join(block[:end + 1])
        err = block[end]
        if re.search(r"Timeout|timed out|Connection reset|RemoteDisconnected|Max retries|Temporary failure|503|502|504|ConnectionError|curl: \(\d+\)", tb):
            return "transient", script, err.strip()[:160]
        return "code", script, tb
    errs = [l for l in lines if "##[error]" in l or re.search(r"\berror\b", l, re.I)]
    tail = [l for l in lines if l.strip()][-15:]
    if re.search(r"Timeout|timed out|Connection reset|503|502|504|rate limit", "\n".join(tail), re.I):
        return "transient", script, (errs[-1] if errs else tail[-1]).strip()[:160]
    return "unknown", script, "\n".join(tail)


def alert(key, title, body):
    if not ASK:
        print("no ASK_SECRET, no alert")
        return
    body_ = json.dumps({"fault": {"key": key, "title": title, "body": body, "url": "/"}})
    heads = {"content-type": "application/json", "x-ask-secret": ASK}
    try:
        # the site's edge turns a bare library client away (403); it is
        # asked as a browser, the way ask.yml asks /ask
        from curl_cffi import requests as rq
        r = rq.post(SITE + "/push", data=body_, headers=heads, impersonate="chrome", timeout=30)
        print("alert:", r.status_code, r.text[:80])
    except ImportError:
        req = urllib.request.Request(SITE + "/push", data=body_.encode(), method="POST")
        for k, v in heads.items():
            req.add_header(k, v)
        req.add_header("User-Agent", "Mozilla/5.0 (Macintosh) arena-triage")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print("alert:", r.read()[:80])
        except Exception as e:
            print("alert failed:", e)
    except Exception as e:
        print("alert failed:", e)


def issue(title, body):
    """One open issue per fault: found by its title, given the new run."""
    q = gh("/repos/%s/issues?state=open&labels=fault&per_page=50" % REPO)
    for it in q if isinstance(q, list) else []:
        if it.get("title") == title:
            gh("/repos/%s/issues/%s/comments" % (REPO, it["number"]), {"body": body})
            print("issue #%s given the run" % it["number"])
            return it["number"]
    try:
        gh("/repos/%s/labels" % REPO, {"name": "fault", "color": "d73a4a", "description": "a failed run on the board, read by build/triage.py"})
    except Exception:
        pass
    it = gh("/repos/%s/issues" % REPO, {"title": title, "body": body, "labels": ["fault"]})
    print("issue #%s opened" % it.get("number"))
    return it.get("number")


def rerun_sweep():
    try:
        gh("/repos/%s/actions/workflows/sweep.yml/dispatches" % REPO, {"ref": "main", "inputs": {"mode": "due"}})
        print("sweep dispatched again")
        return True
    except Exception as e:
        print("could not dispatch:", e)
        return False


def main():
    if not (TOKEN and RUN_ID):
        print("triage: no run to read")
        return 0
    logs = logs_of(RUN_ID)
    if not logs:
        print("no failed job in run", RUN_ID)
        return 0
    job, lines = logs[0]
    kind, script, said = name_it(lines)
    where = "%s%s" % (RUN_NAME or "a run", (" (" + script + ")") if script else "")
    print("kind:", kind, "| where:", where)
    first = said.strip().split("\n")[-1][:140]
    if kind == "login":
        alert("login", "DraftKings logged you out", said)
    elif kind == "transient":
        again = RUN_NAME == "sweep" and rerun_sweep()
        alert("transient@" + RUN_NAME, "%s could not reach its source" % where,
              first + (" -- run again now." if again else " -- it runs again on the next wake."))
    else:
        title = "fault: %s: %s" % (where, first)
        body = ("A failed run: [%s](%s), commit %s, job %s.\n\n```\n%s\n```\n\n"
                "Named by build/triage.py as **%s**. Mend it under CLAUDE.md's rules: read the script, "
                "find the cause, fix it, prove it (run the script dry where it has a dry mode, build the page, "
                "run build/guard.py), then ship with build/ship.sh and close this issue with one line on what it was."
                % (RUN_NAME, RUN_URL, HEAD_SHA, job, said[-6000:], kind))
        issue(title, body)
        alert("code@" + title, "The board hit a fault in %s" % where, first + " -- filed for mending.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
