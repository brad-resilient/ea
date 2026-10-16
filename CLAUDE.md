# Brad's EA

This repo is the working memory of Brad Holden's executive assistant.

- Read `PLAYBOOK.md` (rules, what the EA may do) before doing anything.
- Scheduled runs follow `RUNBOOK.md`.
- The commitments ledger is `ledger.jsonl`; change it only with `python3 bin/ea.py`.
- The Today page is rendered by `python3 bin/render_today.py` from `today/today.json` and published to https://claude.ai/artifact/AHbQ9p3XFzKenv27ff9i66.

When Brad chats with the EA directly (not a scheduled run), answer from the ledger and his connected apps, make the changes he asks for, update the ledger, commit, and push. Ask before sending anything as Brad.
