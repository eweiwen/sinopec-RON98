#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清洗 raw_pois.json -> stations.json

规则（2026-09-24 数据质检结论）：
  1) 名称不含"中国石化"的剔除（高德 010101 分类噪音，仅个别民营挂靠站）；
  2) 深汕特别合作区重分类：汕尾域内 地址含"深汕" ∪ 名称含"深圳" ∪ 地址含"科教大道"
     （矩形法会误收海丰县城，弃用）；
  3) 状态三态：confirmed(已核实)/unverified(待核实)/unlikely(疑似不参与)。
     首版全部 unverified——"爱跑98"关键词命中经人工检查多为其他品牌标签噪音，不作核实证据，
     仅记入 hint 字段作为弱提示；
  4) 名称含"暂停营业"的记入 remark，仍保留（可现场复核）；
  5) 坐标保持 GCJ-02，直接适配高德 JS API。
"""
import json
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TODAY = date.today().isoformat()

CITY_ORDER = ["深圳", "珠海", "广州", "惠州", "东莞", "汕头", "肇庆", "深汕特别合作区"]

# 顺序敏感：先排除噪音，再做深汕重分类
def is_sinopec(name: str) -> bool:
    return ("中国石化" in name) or ("中石化" in name)


def to_shenshan(name: str, addr: str) -> bool:
    # 收紧为全称匹配："深汕高速"字面匹配会把陆丰内湖服务区误收进来
    return (("深汕特别合作区" in addr) or ("深汕合作区" in addr)
            or ("深圳" in name) or ("科教大道" in addr))


def main():
    raw = json.load(open(os.path.join(DATA, "raw_pois.json"), encoding="utf-8"))
    hits = json.load(open(os.path.join(DATA, "raw_aipao_hits.json"), encoding="utf-8"))
    hit_ids = set(hits.keys())

    stations, dropped = [], []
    for city, pois in raw.items():
        for p in pois:
            name = (p.get("name") or "").strip()
            addr = (p.get("address") or "").strip()
            if not is_sinopec(name):
                dropped.append(f"{city}|{name}")
                continue
            try:
                lng, lat = [float(x) for x in p["location"].split(",")]
            except Exception:
                dropped.append(f"{city}|{name}|bad-location")
                continue
            ccity, cdist = city, (p.get("adname") or "").strip()
            if city == "汕尾" and to_shenshan(name, addr):
                ccity, cdist = "深汕特别合作区", "深汕特别合作区"
            remark = "高德标注暂停营业" if "暂停营业" in name else ""
            # 启发式：名称含加盟/联营/特许特征 -> 疑似不参与（活动限自营站）
            status = "unverified"
            if any(k in name for k in ("加盟", "联营", "特许")):
                status = "unlikely"
            stations.append({
                "id": p["id"],
                "name": name.replace("(暂停营业)", "").replace("（暂停营业）", "").strip(),
                "city": ccity,
                "district": cdist,
                "address": addr,
                "tel": (p.get("tel") or "").strip(),
                "lng": lng,
                "lat": lat,
                "status": status,
                "hint": "aipao" if p["id"] in hit_ids else "",
                "remark": remark,
            })

    # 状态机：首选序，前端按此渲染
    order = {c: i for i, c in enumerate(CITY_ORDER)}
    stations.sort(key=lambda s: (order.get(s["city"], 99), s["district"], s["name"]))

    counts = {}
    for s in stations:
        counts[s["city"]] = counts.get(s["city"], 0) + 1

    out = {
        "meta": {
            "updated": TODAY,
            "source": "高德开放平台 POI（typecode=010101 中国石化），GCJ-02 坐标",
            "note": "首版站点状态均为待核实；核实路径：易捷加油APP查油品/现场确认/用户反馈",
            "statusMeaning": {
                "confirmed": "已核实：确认自营且销售爱跑98",
                "unverified": "待核实：中石化站点，自营与98号油品待确认",
                "unlikely": "疑似不参与：名称或地址含加盟/联营等特征",
            },
            "counts": counts,
            "total": len(stations),
        },
        "stations": stations,
    }
    path = os.path.join(DATA, "stations.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[完成] 保留 {len(stations)} 座（剔除 {len(dropped)}），写入 {path}")
    for c in CITY_ORDER:
        if c in counts:
            print(f"  {c}: {counts[c]}")
    if dropped:
        print("[剔除明细]", "；".join(dropped))


if __name__ == "__main__":
    main()
