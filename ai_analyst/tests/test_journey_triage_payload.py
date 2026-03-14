import httpx
import pytest

from ai_analyst.api.routers import journey


class _MockResponse:
    status_code = 200
    text = (
        '{"verdict":{"decision":"NO_TRADE","overall_confidence":0.2,'
        '"final_bias":"neutral","no_trade_conditions":["x"]},"run_id":"r1"}'
    )

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "verdict": {
                "decision": "NO_TRADE",
                "overall_confidence": 0.2,
                "final_bias": "neutral",
                "no_trade_conditions": ["x"],
            },
            "run_id": "r1",
        }


@pytest.mark.asyncio
async def test_run_real_triage_for_symbol_includes_api_key_header_when_configured(monkeypatch):
    monkeypatch.setenv("AI_ANALYST_API_KEY", "test-secret")
    monkeypatch.setenv("AI_ANALYST_LOOPBACK_ANALYSE_URL", "http://loopback.local/analyse")
    monkeypatch.setattr(journey, "_current_session", lambda: "London")
    captured: dict[str, object] = {}

    class _MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, files=None, headers=None):
            captured["url"] = url
            captured["files"] = files
            captured["headers"] = headers
            return _MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _MockClient())

    result = await journey.run_real_triage_for_symbol("XAUUSD")

    assert captured["url"] == "http://loopback.local/analyse"
    assert captured["headers"] == {"X-API-Key": "test-secret"}
    files_map = {key: payload[1] for key, payload in captured["files"]}
    assert files_map["timeframes"] == '["H4", "H1", "M15"]'
    assert files_map["max_daily_risk"] == "1.5"
    assert "smoke_mode" not in files_map
    assert result["symbol"] == "XAUUSD"


@pytest.mark.asyncio
async def test_run_real_triage_for_symbol_omits_auth_header_when_unconfigured(monkeypatch):
    monkeypatch.delenv("AI_ANALYST_API_KEY", raising=False)
    monkeypatch.setattr(journey, "_current_session", lambda: "London")
    captured: dict[str, object] = {}

    class _MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, files=None, headers=None):
            captured["headers"] = headers
            return _MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _MockClient())

    await journey.run_real_triage_for_symbol("XAUUSD")

    assert captured["headers"] == {}


@pytest.mark.asyncio
async def test_triage_smoke_uses_shared_payload_and_auth_header(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_ANALYST_API_KEY", "test-secret")
    monkeypatch.setattr(journey, "_ANALYST_OUTPUT", tmp_path)
    captured: dict[str, object] = {}

    class _MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, files=None, headers=None):
            captured["url"] = url
            captured["files"] = files
            captured["headers"] = headers
            return _MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _MockClient())

    response = await journey.triage_smoke()
    body = response.body.decode("utf-8")

    assert '"loopback_auth_configured":true' in body
    assert captured["headers"] == {"X-API-Key": "test-secret"}
    files_map = {key: payload[1] for key, payload in captured["files"]}
    assert files_map["session"] == "London"
    assert files_map["timeframes"] == '["H4", "H1", "M15"]'
    assert files_map["max_daily_risk"] == "1.5"
    assert files_map["smoke_mode"] == "true"


def test_build_triage_analyse_form_fields_shared_contract():
    normal = journey._build_triage_analyse_form_fields("XAUUSD", "London", smoke_mode=False)
    smoke = journey._build_triage_analyse_form_fields("XAUUSD", "London", smoke_mode=True)

    normal_map = {k: v[1] for k, v in normal}
    smoke_map = {k: v[1] for k, v in smoke}

    assert normal_map["timeframes"] == '["H4", "H1", "M15"]'
    assert normal_map["max_daily_risk"] == "1.5"
    assert "smoke_mode" not in normal_map

    assert smoke_map["timeframes"] == '["H4", "H1", "M15"]'
    assert smoke_map["max_daily_risk"] == "1.5"
    assert smoke_map["smoke_mode"] == "true"
