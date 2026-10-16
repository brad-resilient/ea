#!/usr/bin/env python3
"""Render today.json into today.html (the Today page artifact).

Usage: python3 bin/render_today.py [today.json] [today.html]

today.json fields (all lists may be empty):
  generated_at  ISO time with offset
  run           "Morning brief" | "Midday update" | "End of day" | "Weekly review"
  date_label    e.g. "Friday, October 16"
  headline      one or two sentences: what matters most today
  priorities    [{title, why, ref?, link?}]                up to 5, in priority order
  schedule      [{time, title, detail?, link?}]           today's meetings and blocks
  due           [{ref, title, due, status, who?, link?}]  overdue and due within 7 days
  waiting_on    [{ref, title, who?, since?, link?}]
  drafts        [{kind, title, to?, link?, note?}]        things waiting for Brad's OK
  later         [{date, title, ref?}]                     next ~14 days worth knowing
  done_today    [{title, ref?}]
  notes         [str]
"""
import html
import json
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = ZoneInfo("America/New_York")
E = html.escape


def a(text, link):
    t = E(text or "")
    if link:
        return f'<a href="{E(link, quote=True)}">{t}</a>'
    return t


def ref(r):
    return f'<span class="ref">{E(r)}</span>' if r else ""


def fmt_due(d, today):
    try:
        dd = date.fromisoformat(d)
    except (TypeError, ValueError):
        return "", ""
    delta = (dd - today).days
    label = dd.strftime("%a %b ") + str(dd.day)
    if delta < 0:
        return label, f"{-delta}d overdue"
    if delta == 0:
        return label, "today"
    if delta == 1:
        return label, "tomorrow"
    return label, f"in {delta}d"


def section(title, body, count=None, cls=""):
    c = f'<span class="count">{count}</span>' if count is not None else ""
    return f'<section class="block {cls}"><h2>{E(title)}{c}</h2>{body}</section>'


def empty(text):
    return f'<p class="empty">{E(text)}</p>'


def render(d):
    gen = d.get("generated_at")
    try:
        g = datetime.fromisoformat(gen).astimezone(TZ)
    except (TypeError, ValueError):
        g = datetime.now(TZ)
    today = g.date()
    stamp = g.strftime("%-I:%M %p").lower()
    date_label = d.get("date_label") or g.strftime("%A, %B ") + str(g.day)

    pr = d.get("priorities") or []
    pr_html = "<ol class='prio'>" + "".join(
        f"<li><div class='p-title'>{a(p.get('title'), p.get('link'))}{ref(p.get('ref'))}</div>"
        + (f"<div class='p-why'>{E(p['why'])}</div>" if p.get("why") else "") + "</li>"
        for p in pr) + "</ol>" if pr else empty("No priorities set yet.")

    sc = d.get("schedule") or []
    sc_html = "<ul class='sched'>" + "".join(
        f"<li><span class='time'>{E(s.get('time',''))}</span><div class='s-body'><div class='s-title'>{a(s.get('title'), s.get('link'))}</div>"
        + (f"<div class='s-detail'>{E(s['detail'])}</div>" if s.get("detail") else "") + "</div></li>"
        for s in sc) + "</ul>" if sc else empty("Nothing on the calendar.")

    du = d.get("due") or []
    rows = []
    for it in du:
        label, rel = fmt_due(it.get("due"), today)
        over = rel.endswith("overdue")
        st = it.get("status", "open")
        chip = "over" if over else ("today" if rel in ("today", "tomorrow") else "soon")
        rows.append(
            f"<li class='due-row'><span class='chip {chip}'>{E(rel or label)}</span>"
            f"<div class='d-body'><div class='d-title'>{a(it.get('title'), it.get('link'))}{ref(it.get('ref'))}</div>"
            f"<div class='d-meta'>{E(label)}" + (f" · {E(it['who'])}" if it.get("who") else "")
            + (" · <span class='unclear'>needs checking</span>" if st == "unclear" else "") + "</div></div></li>")
    du_html = "<ul class='due'>" + "".join(rows) + "</ul>" if rows else empty("Nothing due in the next week.")

    wo = d.get("waiting_on") or []
    wo_html = "<ul class='plain'>" + "".join(
        f"<li>{a(w.get('title'), w.get('link'))}{ref(w.get('ref'))}"
        + (f"<span class='meta'>{E(w['who'])}" + (f", since {E(w['since'])}" if w.get('since') else "") + "</span>" if w.get("who") else "")
        + "</li>" for w in wo) + "</ul>" if wo else empty("Not waiting on anyone.")

    dr = d.get("drafts") or []
    dr_html = "<ul class='plain drafts'>" + "".join(
        f"<li><span class='kind'>{E(x.get('kind','draft'))}</span>{a(x.get('title'), x.get('link'))}"
        + (f"<span class='meta'>to {E(x['to'])}</span>" if x.get("to") else "")
        + (f"<span class='meta'>{E(x['note'])}</span>" if x.get("note") else "") + "</li>" for x in dr) + "</ul>" \
        if dr else empty("No drafts waiting for you.")

    la = d.get("later") or []
    la_rows = []
    for x in la:
        lbl, _ = fmt_due(x.get("date"), today)
        la_rows.append(f"<li><span class='l-date'>{E(lbl or x.get('date',''))}</span><span>{E(x.get('title',''))}{ref(x.get('ref'))}</span></li>")
    la_html = "<ul class='later'>" + "".join(la_rows) + "</ul>" if la_rows else empty("Nothing notable coming up.")

    dt = d.get("done_today") or []
    dt_html = ("<ul class='plain done'>" + "".join(f"<li>{E(x.get('title',''))}{ref(x.get('ref'))}</li>" for x in dt) + "</ul>") if dt else ""

    notes = d.get("notes") or []
    notes_html = ("<ul class='plain notes'>" + "".join(f"<li>{E(n)}</li>" for n in notes) + "</ul>") if notes else ""

    left = section("Priorities", pr_html, cls="prio-block") + section("Due and overdue", du_html, len(du))
    right = section("Today's schedule", sc_html) + section("Drafts for your OK", dr_html, len(dr)) \
        + section("Waiting on others", wo_html, len(wo)) + section("Coming up", la_html)
    tail = ""
    if dt_html:
        tail += section("Done today", dt_html)
    if notes_html:
        tail += section("Notes", notes_html)

    with open(os.path.join(ROOT, "today", "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    return (tpl.replace("{{RUN}}", E(d.get("run", "Update")))
               .replace("{{STAMP}}", E(stamp))
               .replace("{{DATE}}", E(date_label))
               .replace("{{HEADLINE}}", E(d.get("headline", "")))
               .replace("{{LEFT}}", left)
               .replace("{{RIGHT}}", right)
               .replace("{{TAIL}}", tail))


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "today", "today.json")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "today", "today.html")
    with open(src, encoding="utf-8") as f:
        d = json.load(f)
    out = render(d)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote {dst} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
