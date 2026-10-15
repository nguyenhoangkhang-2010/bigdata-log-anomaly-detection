"""Sinh dashboard Kibana (data view + Lens + dashboard) thành tệp NDJSON để nạp bằng API Saved Objects.

    python dashboard/kibana/build_saved_objects.py                 # ghi dashboard/kibana/saved_objects/dashboard.ndjson
    curl -X POST -H "kbn-xsrf: true" --form file=@dashboard/kibana/saved_objects/dashboard.ndjson \
         "http://localhost:5601/api/saved_objects/_import?overwrite=true"

Dashboard: http://localhost:5601/app/dashboards#/view/logad-dashboard
Khoảng thời gian mặc định đặt cứng theo dữ liệu (09–12/11/2008) vì log HDFS_v1 là log cũ, không phải "15 phút gần nhất".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).parent / "saved_objects" / "dashboard.ndjson"
VERSION = "8.15.3"
# Phiên bản migration: thiếu thì Kibana coi đối tượng là rất cũ và chạy lại mọi migration (Lens sẽ lỗi vì state đã ở dạng formBased)
CORE_MIGRATION = "8.8.0"
TYPE_MIGRATION = {"index-pattern": "8.0.0", "lens": "8.9.0", "dashboard": "10.2.0"}
TIME_FROM, TIME_TO = "2008-11-09T00:00:00.000Z", "2008-11-12T00:00:00.000Z"

# data view: id -> (tên index, trường thời gian)
VIEWS = {
    "logad-error-stats": ("logad-error-stats", "ts"),
    "logad-anomalies": ("logad-anomalies", "first_ts"),
    "logad-spikes": ("logad-spikes", "ts"),
}


# ---------------------------------------------------------------- cột Lens
def count(label: str = "Số lượng", flt: str | None = None) -> dict:
    col = {"label": label, "dataType": "number", "operationType": "count", "isBucketed": False, "scale": "ratio",
           "sourceField": "___records___", "params": {"emptyAsNull": True}}
    if flt:
        col["filter"] = {"query": flt, "language": "kuery"}
    return col


def agg(op: str, field: str, label: str, flt: str | None = None) -> dict:
    col = {"label": label, "dataType": "number", "operationType": op, "isBucketed": False, "scale": "ratio",
           "sourceField": field, "params": {"emptyAsNull": True}}
    if flt:
        col["filter"] = {"query": flt, "language": "kuery"}
    return col


def date_hist(field: str, label: str = "Thời gian") -> dict:
    return {"label": label, "dataType": "date", "operationType": "date_histogram", "sourceField": field,
            "isBucketed": True, "scale": "interval",
            "params": {"interval": "auto", "includeEmptyRows": True, "dropPartials": False}}


def terms(field: str, label: str, order_by: str, size: int = 10, order: str = "desc") -> dict:
    return {"label": label, "dataType": "string", "operationType": "terms", "scale": "ordinal", "sourceField": field,
            "isBucketed": True,
            "params": {"size": size, "orderBy": {"type": "column", "columnId": order_by}, "orderDirection": order,
                       "otherBucket": False, "missingBucket": False, "parentFormat": {"id": "terms"}}}


def histogram(field: str, label: str) -> dict:
    return {"label": label, "dataType": "number", "operationType": "range", "sourceField": field, "isBucketed": True,
            "scale": "interval",
            "params": {"type": "histogram", "ranges": [{"from": 0, "to": 1000, "label": ""}], "maxBars": 30}}


def lens(oid: str, title: str, vis_type: str, view: str, columns: dict, visualization: dict) -> dict:
    columns = {k: {**v, "customLabel": True} for k, v in columns.items()}  # dùng nhãn tiếng Việt thay vì nhãn tự sinh ("Sum of n")
    layer = {"columns": columns, "columnOrder": list(columns), "incompleteColumns": {}, "sampling": 1}
    return {
        "id": oid, "type": "lens",
        "attributes": {
            "title": title, "description": "", "visualizationType": vis_type,
            "state": {
                "visualization": visualization, "query": {"query": "", "language": "kuery"}, "filters": [],
                "datasourceStates": {"formBased": {"layers": {"l1": layer}}},
            },
        },
        "references": [{"type": "index-pattern", "id": view, "name": "indexpattern-datasource-layer-l1"}],
    }


def metric(oid: str, title: str, view: str, col: dict, subtitle: str = "") -> dict:
    return lens(oid, title, "lnsMetric", view, {"m": col},
                {"layerId": "l1", "layerType": "data", "metricAccessor": "m", "subtitle": subtitle})


def xy(oid: str, title: str, view: str, columns: dict, series: str, x: str, y: list[str], split: str | None = None) -> dict:
    layer = {"layerId": "l1", "layerType": "data", "seriesType": series, "accessors": y, "xAccessor": x, "position": "top",
             "showGridlines": False}
    if split:
        layer["splitAccessor"] = split
    vis = {"legend": {"isVisible": True, "position": "right"}, "valueLabels": "hide", "fittingFunction": "None",
           "preferredSeriesType": series, "layers": [layer]}
    return lens(oid, title, "lnsXY", view, columns, vis)


def table(oid: str, title: str, view: str, columns: dict, shown: list[str]) -> dict:
    vis = {"layerId": "l1", "layerType": "data", "columns": [{"columnId": c} for c in shown]}
    return lens(oid, title, "lnsDatatable", view, columns, vis)


def donut(oid: str, title: str, view: str, columns: dict, group: str, value: str) -> dict:
    vis = {"shape": "donut", "layers": [{
        "layerId": "l1", "layerType": "data", "primaryGroups": [group], "metrics": [value], "numberDisplay": "percent",
        "categoryDisplay": "default", "legendDisplay": "show", "nestedLegend": False,
    }]}
    return lens(oid, title, "lnsPie", view, columns, vis)


# ---------------------------------------------------------------- các panel
def panels() -> list[tuple[dict, tuple[int, int, int, int]]]:
    """(đối tượng Lens, (x, y, rộng, cao)) trên lưới 48 cột."""
    es, an, sp = "logad-error-stats", "logad-anomalies", "logad-spikes"
    return [
        (metric("logad-v-lines", "Dòng nhật ký", es, agg("sum", "n", "Dòng nhật ký"), "toàn bộ nhật ký HDFS_v1"), (0, 0, 12, 7)),
        (metric("logad-v-warn", "Dòng WARN", es, agg("sum", "n", "Dòng WARN", "level : WARN"), "dataset không có ERROR/FATAL"), (12, 0, 12, 7)),
        (metric("logad-v-flagged", "Block bị KMeans gắn cờ", an, count("Block bị gắn cờ", "kmeans_flag : true"), "trên 575.061 block"), (24, 0, 12, 7)),
        (metric("logad-v-spikes", "Đột biến lỗi", sp, count("Đột biến lỗi"), "(cửa sổ 60 giây, component) có z > 3"), (36, 0, 12, 7)),

        (xy("logad-v-warn-time", "Dòng WARN theo thời gian", es,
            {"x": date_hist("ts"), "y": agg("sum", "n", "Dòng WARN", "level : WARN")}, "area", "x", ["y"]), (0, 7, 30, 15)),
        (xy("logad-v-components", "Component sinh nhiều WARN nhất", es,
            {"x": terms("component", "Component", "y", 8), "y": agg("sum", "n", "Dòng WARN", "level : WARN")},
            "bar_horizontal", "x", ["y"]), (30, 7, 18, 15)),

        (xy("logad-v-anomaly-time", "Block bất thường theo thời gian", an,
            {"x": date_hist("first_ts"), "y": count("Block bị gắn cờ", "kmeans_flag : true")}, "bar", "x", ["y"]), (0, 22, 24, 14)),
        (xy("logad-v-score-hist", "Phân bố điểm KMeans theo nhãn thật", an,
            {"x": histogram("kmeans_score", "Điểm KMeans"), "s": terms("label", "Nhãn thật", "y", 3), "y": count("Số block")},
            "bar_stacked", "x", ["y"], split="s"), (24, 22, 24, 14)),

        (donut("logad-v-flagged-by", "Mô hình nào gắn cờ", an,
               {"g": terms("flagged_by", "Mô hình gắn cờ", "m", 7), "m": count("Số block", "NOT flagged_by : \"\"")}, "g", "m"),
         (0, 36, 16, 15)),
        (table("logad-v-top-blocks", "Block bất thường điểm cao nhất", an,
               {"b": terms("block_id", "Block", "s", 10), "s": agg("max", "kmeans_score", "Điểm KMeans"),
                "i": agg("max", "iforest_score", "Điểm Isolation Forest"), "n": agg("max", "n_lines", "Số dòng")},
               ["b", "s", "i", "n"]), (16, 36, 32, 15)),

        (table("logad-v-spike-table", "Component có đột biến lỗi mạnh nhất", sp,
               {"c": terms("component", "Component", "z", 8), "z": agg("max", "z", "z cao nhất"), "k": count("Số cửa sổ đột biến"),
                "n": agg("max", "n", "Số dòng lỗi lớn nhất")}, ["c", "z", "k", "n"]), (0, 51, 48, 12)),
    ]


def build() -> list[dict]:
    objs: list[dict] = []
    for vid, (title, tf) in VIEWS.items():
        objs.append({"id": vid, "type": "index-pattern", "attributes": {"title": title, "name": title, "timeFieldName": tf}, "references": []})
    refs, plist = [], []
    for i, (lens_obj, (x, y, w, h)) in enumerate(panels(), 1):
        objs.append(lens_obj)
        pid = f"p{i}"
        plist.append({"version": VERSION, "type": "lens", "gridData": {"x": x, "y": y, "w": w, "h": h, "i": pid},
                      "panelIndex": pid, "embeddableConfig": {}, "panelRefName": f"panel_{pid}"})
        refs.append({"name": f"{pid}:panel_{pid}", "type": "lens", "id": lens_obj["id"]})
    objs.append({
        "id": "logad-dashboard", "type": "dashboard",
        "attributes": {
            "title": "LogAD – Thống kê lỗi và cảnh báo bất thường",
            "description": "Nhật ký HDFS_v1: số dòng lỗi theo thời gian, component sinh lỗi, block bị mô hình gắn cờ, đột biến lỗi.",
            "panelsJSON": json.dumps(plist), "timeRestore": True, "timeFrom": TIME_FROM, "timeTo": TIME_TO,
            "refreshInterval": {"pause": True, "value": 0},
            "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "syncCursor": True, "syncTooltips": False, "hidePanelTitles": False}),
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})},
        },
        "references": refs,
    })
    return objs


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252 không in được tiếng Việt
    OUT.parent.mkdir(parents=True, exist_ok=True)
    objs = build()
    for o in objs:
        o["coreMigrationVersion"] = CORE_MIGRATION
        o["typeMigrationVersion"] = TYPE_MIGRATION[o["type"]]
    OUT.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in objs) + "\n", encoding="utf-8")
    print(f"đã ghi {len(objs)} đối tượng -> {OUT}")
