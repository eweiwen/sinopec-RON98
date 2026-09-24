# -*- coding: utf-8 -*-
"""匹配东莞官方 68 座 vs stations.json 中的东莞 POI（136 座）"""
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

official = json.loads((DATA / "wx_dg_stations.json").read_text(encoding="utf-8"))["stations"]
stations_doc = json.loads((DATA / "stations.json").read_text(encoding="utf-8"))
pois = [s for s in stations_doc["stations"] if s.get("city") == "东莞"]

def strip_prefix(name: str) -> str:
    for p in ("中国石化", "中石化", "东莞", "东莞石油"):
        if name.startswith(p):
            name = name[len(p):]
    for s in ("加油站", "加油加气站", "加氢站", "服务站", "加气站"):
        if name.endswith(s):
            name = name[: -len(s)]
    return name.strip()

# 建索引
poi_short_map = {}
for p in pois:
    short = strip_prefix(p["name"])
    poi_short_map.setdefault(short, []).append(p)

results = {"exact": [], "alias": [], "no_match": []}
used = set()

# 第一轮：精确匹配
for o in official:
    key = strip_prefix(o["name"])
    if key in poi_short_map and len(poi_short_map[key]) == 1:
        p = poi_short_map[key][0]
        if p["id"] not in used:
            results["exact"].append((o["no"], o["name"], p["id"], p["name"], p["address"]))
            used.add(p["id"])

# 第二轮：官方站名含于 POI 站名（子串），或 POI 站名含于官方站名
for o in official:
    if any(r[0] == o["no"] for r in results["exact"]):
        continue
    o_key = strip_prefix(o["name"])
    matches = []
    for p in pois:
        if p["id"] in used:
            continue
        p_key = strip_prefix(p["name"])
        if o_key in p_key or p_key in o_key:
            matches.append(p)
    if len(matches) == 1:
        p = matches[0]
        results["alias"].append((o["no"], o["name"], p["id"], p["name"], p["address"], "sub_string"))
        used.add(p["id"])
    elif len(matches) > 1:
        # 取相似最高的
        best = max(matches, key=lambda p: SequenceMatcher(None, o_key, strip_prefix(p["name"])).ratio())
        results["alias"].append((o["no"], o["name"], best["id"], best["name"], best["address"], "sub_multi"))
        used.add(best["id"])

# 第三轮：无匹配
for o in official:
    if any(r[0] == o["no"] for r in results["exact"] + results["alias"]):
        continue
    o_key = strip_prefix(o["name"])
    # 找最相似的候选
    best, best_score = None, 0.0
    for p in pois:
        if p["id"] in used:
            continue
        s = SequenceMatcher(None, o_key, strip_prefix(p["name"])).ratio()
        if s > best_score:
            best_score, best = s, p
    results["no_match"].append((o["no"], o["name"], best["id"] if best else "", best["name"] if best else "", best_score))

print("=== 东莞官方 68 座 vs 高德 POI 匹配 ===\n")
print(f"精确匹配: {len(results['exact'])} 座")
for r in results["exact"]:
    print(f"  #{r[0]:>2} {r[1]:<22} → {r[2]} {r[3]}")

print(f"\n子串/别名匹配: {len(results['alias'])} 座")
for r in results["alias"]:
    print(f"  #{r[0]:>2} {r[1]:<22} → {r[2]} {r[3]}  ({r[5]})")

print(f"\n未匹配: {len(results['no_match'])} 座")
for r in results["no_match"]:
    print(f"  #{r[0]:>2} {r[1]:<22} | 最近似: {r[2]} {r[3]} (相似度 {r[4]:.2f})")

# 导出
export = {
    "meta": {
        "official_count": len(official),
        "exact_match": len(results["exact"]),
        "alias_match": len(results["alias"]),
        "no_match": len(results["no_match"]),
    },
    "exact": results["exact"],
    "alias": results["alias"],
    "no_match": results["no_match"],
}
(DATA / "wx_dg_match.json").write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n导出到 data/wx_dg_match.json")
