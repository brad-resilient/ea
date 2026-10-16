# EA Runbook

Steps for each scheduled run. Read `PLAYBOOK.md` first; its rules apply to every step here. Jobs: `morning`, `midday`, `wrap`, `weekly`.

## 1. Start (every job)

1. Get the current time (America/New_York).
2. Run `python3 bin/ea.py begin <job>`.
   - `SKIP …` → end the run with one line: "<job> already ran today." Nothing else.
   - `RUN since=<iso>` → keep `since` as the capture watermark.
3. Read `PLAYBOOK.md` and this file in full. They may have changed since the last run.
4. Run `python3 bin/ea.py list` to load the current open items.

## 2. Capture (morning, midday, wrap, weekly)

Look only at activity after `since` (minus 15 minutes of overlap). Convert to Unix seconds for Gmail and Slack.

1. **Gmail**
   - Sent mail: `in:sent after:<unix>`. New commitments by Brad; replies that close existing items.
   - Inbox: `in:inbox after:<unix> -category:promotions -category:social -category:forums`. Requests from real people, things others promised, deadlines, money and compliance notices.
   - Read a full thread (PLAIN_TEXT) only when the snippet isn't enough.
2. **Slack** (read only): Brad's own messages (`from:<@U03AL729TKR> after:<date>`) and messages to or mentioning him, including DMs. Brad's key DMs are with Charlie Proctor and Kevin Chou.
3. **Otter**: meetings created since `since`. Use summaries and action items; fetch the transcript only to confirm who committed.
4. **Calendar**: events from now through the next 3 business days, for prep and conflicts; new invites needing a response.
5. **Formwork** (morning and weekly only): open tasks assigned to Brad and reviews waiting on him. Read only.

For each finding: `ea.py find <keyword>` first, then `add`, `update` (append the source), `note`, or `close` per the playbook's capture rules. Run `ea.py validate` at the end of capture.

## 3. Job-specific work

### morning (weekdays 6:45)
1. Capture (above), covering overnight.
2. Pick today's priorities (playbook rules).
3. Today's schedule: every event today with a one-line prep note where useful. Note conflicts with Childcare or DNS.
4. Drafts: up to 5 Gmail drafts for replies Brad owes where the content is clear from the thread (acknowledgements, scheduling, sending something that exists). Don't draft anything that needs a decision only Brad can make; list it as a priority instead.
5. Holds: up to 2 prep or focus holds today or tomorrow, per the playbook.
6. Build `today/today.json` with `run: "Morning brief"` (fields in `bin/render_today.py`). `due` = open/unclear items overdue or due within 7 days (`ea.py due --days 7`). `waiting_on` = open `waiting_on` items. `later` = notable items 8–14 days out.

### midday (weekdays 12:52)
1. Capture since the morning run.
2. Update `today/today.json`: keep the morning's priorities unless something more urgent arrived (say so in the headline); move finished items to `done_today`; add new drafts. `run: "Midday update"`.

### wrap (Mon–Thu 5:22)
1. Capture since midday.
2. Mark what got done today (evidence only) and list it in `done_today`.
3. Set the headline to what slipped and the first thing for tomorrow. `priorities` = tomorrow's top 3. `schedule` = tomorrow's events with prep notes. `run: "End of day"`.
4. Drafts or holds for tomorrow's prep, within the limits.

### weekly (Fri 4:22)
1. Capture since midday.
2. Review the whole ledger:
   - `unclear` items older than 5 days: check sources again; close, keep, or ask Brad in the notes.
   - `waiting_on` items older than 7 days: draft a polite nudge (counts toward the 5-draft limit) or list it.
   - Commitments with no due date older than 10 days: suggest a date or dropping it, in notes.
3. Today page as a weekly review: `run: "Weekly review"`; headline = the week in one or two sentences; `done_today` = what closed this week; `priorities` = next week's top 3–5; `later` = next week's dated items; notes = decisions Brad should make about stale items.

## 4. Finish (every job)

1. `python3 bin/ea.py validate`.
2. `python3 bin/render_today.py` to build `today/today.html`.
3. Publish the Today page to the same URL:
   - `Artifact` with `action: "read"`, `url: https://claude.ai/artifact/AHbQ9p3XFzKenv27ff9i66` (required before updating it from a new session).
   - `Artifact` publish with `url` set to that URL and `file_path` set to `today/today.html`. No `icon`. If the publish is refused with a conflict, publish once more with the same file; the page is regenerated whole each run.
4. `python3 bin/ea.py finish <job> --summary "<one line>"`.
5. Commit and push: `git add -A && git commit -m "<job> <date>: <n> added, <n> closed" && git push`. If the push is rejected, `git pull --rebase` once and push again.
6. Final message for Brad (this is what his phone notification shows), in this shape:
   - One line: the headline.
   - The priorities, one line each.
   - Drafts and holds created, one line each.
   - Anything that needs his decision or looked suspicious.
   - The Today page link.
   Keep it under 15 lines. No recap of the steps.

## If something fails

- A source is unreachable: skip it, say which in the final message and in the Today page notes, and carry on.
- The repo can't be cloned or pushed: still send the final message with the brief, and say the ledger wasn't updated.
- The Today page can't be published: put the full brief in the final message instead.
