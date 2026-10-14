"""Kiểm tra backend đúng hợp đồng api/openapi.yaml (API-first).

1. Cấu trúc: cùng tập route/method/operationId/tham số, cùng thuộc tính + required của schema.
2. Hành vi: phản hồi thật của từng endpoint hợp lệ với schema trong hợp đồng.
"""
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

SPEC = yaml.safe_load((Path(__file__).resolve().parents[2] / "api" / "openapi.yaml").read_text(encoding="utf-8"))
HTTP = {"get", "post", "put", "patch", "delete"}


def _ref_name(schema: dict) -> str | None:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if schema.get("type") == "array" and "$ref" in schema.get("items", {}):
        return "[]" + schema["items"]["$ref"].rsplit("/", 1)[-1]
    return None


def _resp_name(op: dict) -> str | None:
    ok = op["responses"].get("200", {})
    return _ref_name(ok.get("content", {}).get("application/json", {}).get("schema", {}))


@pytest.fixture(scope="module")
def generated(client):
    return client.app.openapi()


def test_same_operations(generated):
    spec_ops = {(p, m): op for p, item in SPEC["paths"].items() for m, op in item.items() if m in HTTP}
    app_ops = {(p, m): op for p, item in generated["paths"].items() for m, op in item.items() if m in HTTP}
    assert set(spec_ops) == set(app_ops), f"khác route: {set(spec_ops) ^ set(app_ops)}"
    for key, sop in spec_ops.items():
        aop = app_ops[key]
        assert sop["operationId"] == aop["operationId"], key
        sp = {(p["in"], p["name"]) for p in sop.get("parameters", [])}
        ap = {(p["in"], p["name"]) for p in aop.get("parameters", [])}
        assert sp == ap, f"{key}: tham số khác nhau {sp ^ ap}"
        assert _resp_name(sop) == _resp_name(aop), f"{key}: schema phản hồi 200 khác nhau"


def _enum_of(prop: dict, schemas: dict) -> set | None:
    """Tập giá trị enum của một thuộc tính (đi qua $ref và anyOf), bỏ null. None nếu không phải enum."""
    if "$ref" in prop:
        return _enum_of(schemas[prop["$ref"].rsplit("/", 1)[-1]], schemas)
    if "enum" in prop:
        return set(prop["enum"]) - {None}
    for branch in prop.get("anyOf", []):
        found = _enum_of(branch, schemas)
        if found:
            return found
    return None


def test_same_schemas(generated):
    # FastAPI nhúng thẳng Literal vào thuộc tính nên schema enum rời (Level, Severity...) không xuất hiện;
    # ta so giá trị enum ngay trong từng thuộc tính.
    app_schemas = generated["components"]["schemas"]
    spec_schemas = SPEC["components"]["schemas"]
    for name, s in spec_schemas.items():
        if name == "Problem" or s.get("type") != "object" or "properties" not in s:
            continue
        assert name in app_schemas, f"thiếu schema {name}"
        a = app_schemas[name]
        assert set(s["properties"]) == set(a["properties"]), f"{name}: thuộc tính khác nhau"
        assert set(s.get("required", [])) == set(a.get("required", [])), f"{name}: required khác nhau"
        for prop, sp in s["properties"].items():
            se = _enum_of(sp, spec_schemas)
            if se:
                assert se == _enum_of(a["properties"][prop], app_schemas), f"{name}.{prop}: enum khác nhau"


def _validate(client, path: str, schema_ref: str, **params):
    r = client.get(path, params=params)
    assert r.status_code == 200, r.text
    root = {"$ref": f"#/components/schemas/{schema_ref}", "components": SPEC["components"]}
    errs = list(Draft202012Validator(root).iter_errors(r.json()))
    assert not errs, [e.message for e in errs[:3]]
    return r.json()


def _validate_list(client, path: str, item_ref: str, **params):
    r = client.get(path, params=params)
    assert r.status_code == 200, r.text
    root = {"type": "array", "items": {"$ref": f"#/components/schemas/{item_ref}"}, "components": SPEC["components"]}
    errs = list(Draft202012Validator(root).iter_errors(r.json()))
    assert not errs, [e.message for e in errs[:3]]
    return r.json()


def test_responses_match_contract(client):
    _validate(client, "/api/v1/health", "Health")
    _validate(client, "/api/v1/meta", "Meta")
    _validate(client, "/api/v1/overview/summary", "Summary")
    _validate(client, "/api/v1/overview/timeline", "Timeline", bucket="15m")
    _validate_list(client, "/api/v1/overview/components", "ComponentStat")
    _validate_list(client, "/api/v1/alerts", "Alert")
    page = _validate(client, "/api/v1/anomalies", "AnomalyPage")
    _validate(client, f"/api/v1/anomalies/{page['items'][0]['block_id']}", "AnomalyDetail")
    _validate_list(client, "/api/v1/events", "EventTemplate")
    _validate_list(client, "/api/v1/models", "ModelEval")
    _validate(client, "/api/v1/models/kmeans/score-distribution", "ScoreDistribution")
    _validate(client, "/api/v1/logs", "LogPage", level="ERROR")
