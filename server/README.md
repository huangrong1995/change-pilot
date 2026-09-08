# Change Pilot Agent Server (V1, Phase 1–4)

FastAPI app that exposes the `change-pilot` skill over HTTP.

## Run

```bash
cd /home/workspace/code/github/change_pilot_customer
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

## Tests

```bash
pytest server/tests -v
```