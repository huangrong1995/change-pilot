# Change Pilot Agent Server (V1, Phase 1–4)

FastAPI app that exposes the `change-pilot` skill over HTTP.

## Quick start (recommended)

```bash
cd /home/workspace/code/github/change_pilot_customer
cp server/.env.example .env        # then set a real CHANGE_PILOT_API_TOKEN
./server/run.sh start              # creates .venv on first run, starts in background
```

The launcher handles the virtualenv, dependency install, and setting up a
local `CHANGE_PILOT_API_TOKEN`/`CHANGE_PILOT_SKILL_DIR`. Settings come from
`.env`, or `CHANGE_PILOT_*` env vars you export (exported vars win). On
first run the skill is picked up from `~/.claude/skills/change-pilot`.

Lifecycle commands:

```bash
./server/run.sh status      # is it running?
./server/run.sh logs        # follow the log (also at .run/change-pilot.log)
./server/run.sh restart
./server/run.sh stop
./server/run.sh foreground  # run in the current shell for debugging
```

## Advanced / manual start

For an alternative to the launcher:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
export CHANGE_PILOT_API_TOKEN=dev-token
export CHANGE_PILOT_SKILL_DIR=$(pwd)/.claude/skills/change-pilot
# ensure skill is installed:
./install.sh --target=claude-code --prefix=$(pwd)/.claude
uvicorn server.app.main:app --host 0.0.0.0 --port 8080
```

## Try it

```bash
curl -sS http://localhost:8080/health
curl -sS -X POST http://localhost:8080/v1/change-pilot \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{"raw_text":"修复扫码过程中图像数据未及时清理的问题，提升扫码稳定性。"}'
```

## Status

Phase 1–4 complete: end-to-end `POST /v1/change-pilot` works with mocked
and real `claude -p`. See `docs/superpowers/plans/2026-09-08-server-implementation.md`.

## Tests

```bash
pytest server/tests -v
```