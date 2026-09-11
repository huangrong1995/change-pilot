# Change Pilot Agent Server

FastAPI app that exposes the `change-pilot` skill over HTTP via a single,
stateless, direct LLM call.

The server no longer shells out to `claude -p`. Each request loads the
change-pilot skill assets once at startup, builds one ChatGPT-compatible
prompt, makes exactly one model call, validates the output against the skill's
output schema and sensitive-pattern rules, and returns the customer-facing
line.

## Quick start (recommended)

```bash
cd /home/workspace/code/github/change_pilot_customer
cp server/.env.example .env        # set a real CHANGE_PILOT_API_TOKEN + provider config
./server/run.sh start              # creates .venv on first run, starts in background
```

The launcher handles the virtualenv, dependency install, and setting up a local
`CHANGE_PILOT_API_TOKEN`/`CHANGE_PILOT_SKILL_DIR`. Settings come from `.env`, or
`CHANGE_PILOT_*` env vars you export (exported vars win). On first run the skill
is picked up from `~/.claude/skills/change-pilot`.

The server boots even without a configured provider key; `/health` reports
provider readiness, and the route returns a sanitized 502 until a key is set.

Lifecycle commands:

```bash
./server/run.sh status      # is it running?
./server/run.sh logs        # follow the log (also at .run/change-pilot.log)
./server/run.sh restart
./server/run.sh stop
./server/run.sh foreground  # run in the current shell for debugging
```

## Provider configuration (OpenAI-compatible)

The runtime speaks the OpenAI-compatible Chat Completions protocol, so you can
point it at MiniMax, DeepSeek, Qwen, or any compatible endpoint by supplying
only a URL, an API key, and a model name via the environment:

```bash
export CHANGE_PILOT_BASE_URL=https://api.example.com/v1
export CHANGE_PILOT_API_KEY=<your-provider-key>
export CHANGE_PILOT_MODEL=<your-model-name>
```

Optional tuning:

```bash
export CHANGE_PILOT_MAX_TOKENS=1024
export CHANGE_PILOT_PROVIDER_TIMEOUT=60   # seconds
export CHANGE_PILOT_RETRY_COUNT=1         # bounded transient retries
export CHANGE_PILOT_MAX_CONCURRENCY=4     # in-flight model calls
```

The HTTP authentication token (`CHANGE_PILOT_API_TOKEN`) is separate from the
provider API key and is required for every request.

## Advanced / manual start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
export CHANGE_PILOT_API_TOKEN=dev-token
export CHANGE_PILOT_SKILL_DIR=$(pwd)/.claude/skills/change-pilot
export CHANGE_PILOT_BASE_URL=https://api.example.com/v1
export CHANGE_PILOT_API_KEY=...
export CHANGE_PILOT_MODEL=...
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

Default mode returns only `{"customer_output":"扫码功能优化：优化扫码功能，提升扫码稳定性。"}`.
Pass `"mode":"debug"` to also receive the schema-validated `analysis` and
`validation` fields.

## CLI

```bash
/tmp/rt-venv/bin/python -m cli.main --text "修复扫码稳定性问题" \
  --skill-dir "$(pwd)"
```

Default mode prints the customer-facing line; `--mode debug` prints a JSON object.

## Security & privacy

- Bearer-token authentication is required on every request.
- `raw_text`, full prompts, provider payloads, and API keys are never logged.
- Default responses contain only the customer-facing line.
- Model output must pass the skill's `schemas/output.schema.json` and
  `rules/sensitive-patterns.yaml` before it is returned; failures are sanitized errors.

## Status

Lightweight runtime V1 complete: one direct OpenAI-compatible model call per
request, no subprocess, no `claude` CLI. See
`docs/superpowers/plans/2026-09-10-lightweight-runtime-v1.md`.

## Tests

```bash
/tmp/rt-venv/bin/python -m pytest -q server/tests tests_runtime
```

All model calls are mocked; no real provider key is required.