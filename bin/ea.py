#!/usr/bin/env python3
"""Helper for Brad's EA: commitments ledger and run state.

Stdlib only. Run from anywhere; paths resolve to the repo root.

Ledger (ledger.jsonl): one JSON object per line, schema in PLAYBOOK.md.
State (state.json): last runs per job, used for skip decisions and capture watermarks.

Commands
  list   [--status open,unclear] [--type T] [--project P] [--due-by YYYY-MM-DD] [--json]
  due    [--days 7]                 overdue + due within N days (open/unclear only)
  show   ID
  find   TEXT
  add    'JSON'                     add one item (id/created/updated filled in)
  update ID 'JSON' [--note TEXT]    merge fields into an item
  close  ID [--status done|dropped] [--note TEXT]
  note   ID TEXT                    append a dated note
  validate
  projects [--json]                 long-term projects: next step, open items, days since progress
  project ID 'JSON' [--progress TEXT]
                                    update a project's fields (next_step, target, metric, status);
                                    --progress logs dated progress and resets the stale clock
  begin  JOB [--force]              prints RUN since=<iso> or SKIP <reason>
  finish JOB [--summary TEXT]
  state                             print state.json
"""
import json
import os
import sys
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "ledger.jsonl")
STATE = os.path.join(ROOT, "state.json")
PROJECTS = os.path.join(ROOT, "projects.json")
EXTRA_TAGS = {"personal"}
STALE_DAYS = 7
TZ = ZoneInfo("America/New_York")

TYPES = {"commitment", "waiting_on", "request", "deadline", "followup", "event"}
STATUSES = {"open", "unclear", "done", "dropped"}
PRIORITIES = {"high", "medium", "low"}
REQUIRED = {"type", "title"}
PRIO_ORDER = {"high": 0, "medium": 1, "low": 2}


def now():
    return datetime.now(TZ)


def today():
    return now().date()


def load():
    items = []
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError as e:
                    sys.exit(f"ledger.jsonl line {n} is not valid JSON: {e}")
    return items


def save(items):
    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False, sort_keys=False) + "\n")
    os.replace(tmp, LEDGER)


def check(it):
    errs = []
    for k in REQUIRED:
        if not it.get(k):
            errs.append(f"missing {k}")
    if it.get("type") and it["type"] not in TYPES:
        errs.append(f"type must be one of {sorted(TYPES)}")
    if it.get("status") and it["status"] not in STATUSES:
        errs.append(f"status must be one of {sorted(STATUSES)}")
    if it.get("priority") and it["priority"] not in PRIORITIES:
        errs.append(f"priority must be one of {sorted(PRIORITIES)}")
    if it.get("due"):
        try:
            date.fromisoformat(it["due"])
        except ValueError:
            errs.append("due must be YYYY-MM-DD or null")
    if "sources" in it and not isinstance(it["sources"], list):
        errs.append("sources must be a list")
    if it.get("project"):
        ok = {p["id"] for p in load_projects()} | EXTRA_TAGS
        if it["project"] not in ok:
            errs.append(f"project must be one of {sorted(ok)}")
    return errs


def load_projects():
    if not os.path.exists(PROJECTS):
        return []
    with open(PROJECTS, encoding="utf-8") as f:
        return json.load(f)


def save_projects(ps):
    with open(PROJECTS, "w", encoding="utf-8") as f:
        json.dump(ps, f, indent=2, ensure_ascii=False)
        f.write("\n")


def project_summary(items):
    out = []
    for p in sorted(load_projects(), key=lambda x: x.get("order", 99)):
        if p.get("status") != "active":
            continue
        mine = [i for i in items if i.get("project") == p["id"] and i.get("status") in ("open", "unclear")]
        overdue = [i for i in mine if i.get("due") and date.fromisoformat(i["due"]) < today()]
        lp = p.get("last_progress")
        days = (today() - date.fromisoformat(lp)).days if lp else None
        out.append({
            "id": p["id"], "order": p.get("order"), "name": p["name"], "goal": p.get("goal"),
            "target": p.get("target"), "next_step": p.get("next_step"), "metric": p.get("metric"),
            "open": len(mine), "overdue": len(overdue), "last_progress": lp,
            "days_since_progress": days, "stale": days is None or days >= STALE_DAYS,
            "refs": [i["id"] for i in mine],
        })
    return out


def next_id(items):
    nums = [int(i["id"][1:]) for i in items if str(i.get("id", "")).startswith("c") and i["id"][1:].isdigit()]
    return f"c{(max(nums) + 1) if nums else 1:03d}"


def get(items, iid):
    for it in items:
        if it.get("id") == iid:
            return it
    sys.exit(f"no item {iid}")


def sort_key(it):
    d = it.get("due") or "9999-12-31"
    return (d, PRIO_ORDER.get(it.get("priority", "medium"), 1), it.get("id", ""))


def fmt(it):
    due = it.get("due") or "—"
    flag = ""
    if it.get("due") and it.get("status") in ("open", "unclear"):
        if date.fromisoformat(it["due"]) < today():
            flag = " OVERDUE"
    who = it.get("counterparty") or ""
    if it.get("blocked_by"):
        who = (who + " " if who else "") + f"(blocked by {it['blocked_by']})"
    return (f"{it.get('id','?'):5} {it.get('status','?'):8} {it.get('priority','-'):6} "
            f"{due:10}{flag:8} [{it.get('type')}{'/' + it['project'] if it.get('project') else ''}] {it.get('title')}"
            + (f"  — {who}" if who else ""))


def add_note(it, text):
    it.setdefault("notes", [])
    if isinstance(it["notes"], str):
        it["notes"] = [it["notes"]] if it["notes"] else []
    it["notes"].append(f"{today().isoformat()}: {text}")


def parse_flags(args, names):
    out, rest, i = {}, [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and a[2:] in names:
            if names[a[2:]]:
                out[a[2:]] = args[i + 1]
                i += 2
            else:
                out[a[2:]] = True
                i += 1
        else:
            rest.append(a)
            i += 1
    return out, rest


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {"jobs": {}}


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main(argv):
    if not argv:
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    items = load()

    if cmd == "list":
        fl, _ = parse_flags(args, {"status": 1, "type": 1, "project": 1, "due-by": 1, "json": 0})
        sts = set((fl.get("status") or "open,unclear").split(","))
        sel = [i for i in items if i.get("status") in sts or "all" in sts]
        if fl.get("type"):
            sel = [i for i in sel if i.get("type") == fl["type"]]
        if fl.get("project"):
            want = fl["project"]
            sel = [i for i in sel if (i.get("project") or "none") == want]
        if fl.get("due-by"):
            sel = [i for i in sel if i.get("due") and i["due"] <= fl["due-by"]]
        sel.sort(key=sort_key)
        if fl.get("json"):
            print(json.dumps(sel, indent=2, ensure_ascii=False))
        else:
            for i in sel:
                print(fmt(i))
            print(f"({len(sel)} items)")

    elif cmd == "due":
        fl, _ = parse_flags(args, {"days": 1})
        horizon = today() + timedelta(days=int(fl.get("days", 7)))
        open_ids = {i["id"] for i in items if i.get("status") in ("open", "unclear")}
        sel = [i for i in items if i.get("status") in ("open", "unclear") and i.get("due")
               and date.fromisoformat(i["due"]) <= horizon
               and i.get("blocked_by") not in open_ids]
        sel.sort(key=sort_key)
        for i in sel:
            print(fmt(i))
        print(f"({len(sel)} items due by {horizon.isoformat()})")

    elif cmd == "show":
        print(json.dumps(get(items, args[0]), indent=2, ensure_ascii=False))

    elif cmd == "find":
        q = " ".join(args).lower()
        for i in sorted(items, key=sort_key):
            blob = json.dumps(i, ensure_ascii=False).lower()
            if q in blob:
                print(fmt(i))

    elif cmd == "add":
        it = json.loads(args[0])
        it.setdefault("status", "open")
        it.setdefault("priority", "medium")
        it.setdefault("sources", [])
        it.setdefault("notes", [])
        it["id"] = next_id(items)
        it["created"] = it.get("created") or today().isoformat()
        it["updated"] = today().isoformat()
        errs = check(it)
        if errs:
            sys.exit("not added: " + "; ".join(errs))
        items.append(it)
        save(items)
        print(f"added {it['id']}: {it['title']}")

    elif cmd == "update":
        fl, rest = parse_flags(args, {"note": 1})
        it = get(items, rest[0])
        patch = json.loads(rest[1]) if len(rest) > 1 else {}
        patch.pop("id", None)
        if "sources" in patch and isinstance(patch["sources"], list):
            existing = it.get("sources", [])
            for s in patch.pop("sources"):
                if s not in existing:
                    existing.append(s)
            it["sources"] = existing
        it.update(patch)
        if fl.get("note"):
            add_note(it, fl["note"])
        it["updated"] = today().isoformat()
        errs = check(it)
        if errs:
            sys.exit("not updated: " + "; ".join(errs))
        save(items)
        print(f"updated {it['id']}")

    elif cmd == "close":
        fl, rest = parse_flags(args, {"status": 1, "note": 1})
        it = get(items, rest[0])
        it["status"] = fl.get("status", "done")
        if it["status"] not in ("done", "dropped"):
            sys.exit("close status must be done or dropped")
        it["closed"] = today().isoformat()
        if fl.get("note"):
            add_note(it, fl["note"])
        it["updated"] = today().isoformat()
        save(items)
        print(f"closed {it['id']} as {it['status']}")

    elif cmd == "note":
        it = get(items, args[0])
        add_note(it, " ".join(args[1:]))
        it["updated"] = today().isoformat()
        save(items)
        print(f"noted {it['id']}")

    elif cmd == "validate":
        seen, bad = set(), 0
        for n, it in enumerate(items, 1):
            errs = check(it)
            if it.get("id") in seen:
                errs.append("duplicate id")
            seen.add(it.get("id"))
            if errs:
                bad += 1
                print(f"line {n} ({it.get('id')}): " + "; ".join(errs))
        print("ok" if not bad else f"{bad} invalid items")
        if bad:
            sys.exit(1)

    elif cmd == "projects":
        fl, _ = parse_flags(args, {"json": 0})
        summ = project_summary(items)
        if fl.get("json"):
            print(json.dumps(summ, indent=2, ensure_ascii=False))
        else:
            for s in summ:
                age = "never" if s["days_since_progress"] is None else f"{s['days_since_progress']}d ago"
                flag = "  STALE" if s["stale"] else ""
                print(f"{s['order']}. {s['name']} [{s['id']}]  target {s['target'] or 'not set'}  "
                      f"open {s['open']} (overdue {s['overdue']})  last progress {age}{flag}")
                print(f"   next: {s['next_step']}")
                if s.get("metric"):
                    print(f"   metric: {s['metric']}")

    elif cmd == "project":
        fl, rest = parse_flags(args, {"progress": 1})
        ps = load_projects()
        p = next((x for x in ps if x["id"] == rest[0]), None)
        if not p:
            sys.exit(f"no project {rest[0]}")
        patch = json.loads(rest[1]) if len(rest) > 1 else {}
        for k in ("id", "log", "last_progress"):
            patch.pop(k, None)
        if patch.get("target"):
            date.fromisoformat(patch["target"])
        p.update(patch)
        if fl.get("progress"):
            p["last_progress"] = today().isoformat()
            p.setdefault("log", []).append(f"{today().isoformat()}: {fl['progress']}")
        save_projects(ps)
        print(f"updated project {p['id']}")

    elif cmd == "begin":
        fl, rest = parse_flags(args, {"force": 0})
        job = rest[0]
        st = load_state()
        j = st["jobs"].setdefault(job, {})
        last_done = j.get("last_completed")
        if last_done and not fl.get("force"):
            if datetime.fromisoformat(last_done).astimezone(TZ).date() == today():
                print(f"SKIP already completed today at {last_done}")
                return
        # watermark = most recent completed run of ANY job, so sweeps don't re-read old mail
        all_done = [v.get("last_completed") for v in st["jobs"].values() if v.get("last_completed")]
        since = max(all_done) if all_done else (now() - timedelta(days=1)).isoformat(timespec="seconds")
        j["last_started"] = now().isoformat(timespec="seconds")
        save_state(st)
        print(f"RUN since={since}")

    elif cmd == "finish":
        fl, rest = parse_flags(args, {"summary": 1})
        job = rest[0]
        st = load_state()
        j = st["jobs"].setdefault(job, {})
        j["last_completed"] = now().isoformat(timespec="seconds")
        if fl.get("summary"):
            j["last_summary"] = fl["summary"]
        save_state(st)
        print(f"finished {job} at {j['last_completed']}")

    elif cmd == "state":
        print(json.dumps(load_state(), indent=2, ensure_ascii=False))

    else:
        sys.exit(f"unknown command {cmd}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
