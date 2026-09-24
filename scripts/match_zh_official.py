# -*- coding: utf-8 -*-
"""匹配珠海官方 32 座 vs stations.json 中的珠海 POI（67 座）+ 售卡站名单（42 座）"""
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

official = json.loads((DATA / "wx_zh98_stations.json").read_text(encoding="utf-8"))["stations"]
stations_doc = json.loads((DATA / "stations.json").read_text(encoding="utf-8"))
pois = [s for s in stations_doc["stations"] if s.get("city") == "珠海"]
official_list = json.loads((DATA / "sinopec_official_44.json").read_text(encoding="utf-8"))
card_stations = [s for s in official_list.get("stations", []) if "珠海" in (s.get("address") or "")]

def strip_prefix(name: str) -> str:
    for p in ("中国石化", "中石化", "珠海", "广东珠海", "广东"):
        if name.startswith(p):
            name = name[len(p):]
    for s in ("加油站", "加油加气站", "加氢站", "加气站", "服务区加油站", "服务区", "服务站"):
        if name.endswith(s):
            name = name[: -len(s)]
    return name.strip()

poi_short_map = {}
for p in pois:
    short = strip_prefix(p["name"])
    poi_short_map.setdefault(short, []).append(p)

results = {"exact": [], "alias": [], "no_match": []}
used_poi = set()

# 精确
for o in official:
    key = strip_prefix(o["name"])
    if key in poi_short_map and len(poi_short_map[key]) == 1:
        p = poi_short_map[key][0]
        if p["id"] not in used_poi:
            results["exact"].append((o["no"], o["name"], o["addr"], p["id"], p["name"], p["address"]))
            used_poi.add(p["id"])

# 子串
for o in official:
    if any(r[0] == o["no"] for r in results["exact"]):
        continue
    o_key = strip_prefix(o["name"])
    matches = []
    for p in pois:
        if p["id"] in used_poi:
            continue
        p_key = strip_prefix(p["name"])
        if len(o_key) >= 2 and len(p_key) >= 2:
            if o_key in p_key or p_key in o_key:
                matches.append(p)
    if len(matches) == 1:
        p = matches[0]
        results["alias"].append((o["no"], o["name"], o["addr"], p["id"], p["name"], p["address"], "sub"))
        used_poi.add(p["id"])
    elif len(matches) > 1:
        best = max(matches, key=lambda p: SequenceMatcher(None, o_key, strip_prefix(p["name"])).ratio())
        results["alias"].append((o["no"], o["name"], o["addr"], best["id"], best["name"], best["address"], "sub_multi"))
        used_poi.add(best["id"])

# 地址兜底
for o in official:
    if any(r[0] == o["no"] for r in results["exact"] + results["alias"]):
        continue
    best, best_score = None, 0.0
    for p in pois:
        if p["id"] in used_poi:
            continue
        s = SequenceMatcher(None, o["addr"].replace(" ", ""), p.get("address", "").replace(" ", "")).ratio()
        if s > best_score:
            best_score, best = s, p
    if best:
        results["no_match"].append((o["no"], o["name"], o["addr"], best["id"], best["name"], best["address"], round(best_score, 2)))

# 售卡站匹配
def find_card_station(o):
    key = strip_prefix(o["name"])
    for c in card_stations:
        cname = strip_prefix(c.get("name", ""))
        if cname == key:
            return c, "exact"
    for c in card_stations:
        cname = strip_prefix(c.get("name", ""))
        if len(key) >= 2 and len(cname) >= 2 and (key in cname or cname in key):
            return c, "alias"
    for c in card_stations:
        caddr = c.get("address", "").replace(" ", "")
        oaddr = o["addr"].replace(" ", "")
        r = SequenceMatcher(None, oaddr, caddr).ratio()
        if r > 0.5:
            return c, f"addr({r:.2f})"
    return None, ""

card_hits = {}
for o in official:
    c, method = find_card_station(o)
    if c:
        card_hits[o["no"]] = (c.get("name", ""), c.get("address", ""), method)

print(f"=== 珠海官方 32 座 vs 高德珠海 POI {len(pois)} 座 匹配 ===\n")
print(f"精确匹配: {len(results['exact'])} 座")
for r in results["exact"]:
    print(f"  #{r[0]:>2} {r[1]:<20} → {r[3]} {r[4]} | {r[5]}")

print(f"\n子串/别名: {len(results['alias'])} 座")
for r in results["alias"]:
    print(f"  #{r[0]:>2} {r[1]:<20} → {r[3]} {r[4]} | {r[5]}  ({r[6]})")

print(f"\n未匹配 POI: {len(results['no_match'])} 座")
for r in results["no_match"]:
    print(f"  #{r[0]:>2} {r[1]:<20} | 最近似: {r[3]} {r[4]} (addr相似 {r[6]}) | {r[5]}")

print(f"\n售卡站命中（自营佐证）: {len(card_hits)} 座")
for no, (name, addr, method) in sorted(card_hits.items()):
    print(f"  #{no:>2} {name:<20} | {addr} ({method})")

export = {
    "meta": {
        "official_count": len(official),
        "zh_poi_count": len(pois),
        "zh_card_count": len(card_stations),
        "exact_match": len(results["exact"]),
        "alias_match": len(results["alias"]),
        "no_match": len(results["no_match"]),
        "card_station_hits": len(card_hits),
    },
    "exact": results["exact"],
    "alias": results["alias"],
    "no_match": results["no_match"],
    "card_station_hits": {str(k): v for k, v in card_hits.items()},
}
(DATA / "wx_zh98_match.json").write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n导出到 data/wx_zh98_match.json")
