# -*- coding: utf-8 -*-
"""
将「中石化加油卡网上营业厅·加油站网点查询」的广东官方名单
与高德 POI 抓取的 1008 座站点做三级匹配。

策略（2026-09-24 收窄后）：
  - 售卡站匹配结果**只作为后台交叉核查字段**（has_card_network 等），
    不再自动把 status 升级为 confirmed。
  - status 唯一由用户人工核验驱动：
      * confirmed —— 仅当该站在 manual_overrides.json 中被用户按"官方名单核验"标记；
      * unlikely  —— 用户人工标记不参与，或名称/地址含明确合资特征；
      * unverified —— 其他所有站点（含售卡站匹配成功但未人工核实的）。
  - 工作台前台仅展示 confirmed（默认 filter=all，用户按需查看其他状态）。

产出：
  data/stations.json  每座站新增/更新字段：
    - has_card_network: bool  是否命中售卡站自动匹配（后台核查字段）
    - card_network_match_method: phone | name_exact | addr(NN) | ""
    - official_station_name / official_address / official_phone  官方字段回填
  data/match_report.txt  匹配诊断报告
"""
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

AMAP_PREFIX_RE = re.compile(r"^(中国石化|中国石油化工|中石化)\s*")
AMAP_SUFFIX_RE = re.compile(r"(加油加气站|加气加油站|加油站|加气站|充电站|服务[区站]|站点)$")

CITY_PREFIX = ("广东省", "广州市", "深圳市", "珠海市", "惠州市", "东莞市", "中山市",
               "汕头市", "肇庆市", "汕尾市", "江门市", "佛山市", "湛江市", "清远市",
               "河源市", "梅州市", "潮州市", "揭阳市", "云浮市", "韶关市", "茂名市",
               "阳江市")

JV_MARKERS = ["碧辟", "联合石油", "中化", "联营", "合资", "壳牌", "中油碧辟"]


def normalize_phone(p: str) -> str:
    return re.sub(r"[^\d]", "", p or "")


def short_name_from_amap(name: str) -> str:
    n = AMAP_PREFIX_RE.sub("", name or "").strip()
    n = AMAP_SUFFIX_RE.sub("", n).strip()
    return n


def norm_addr(a: str) -> str:
    s = (a or "").strip()
    for p in CITY_PREFIX:
        if s.startswith(p):
            s = s[len(p):]
            break
    s = re.sub(r"[\s\u3000]+", "", s)
    return s


def addr_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_match(poi: dict, officials: list):
    poi_phone = normalize_phone(poi.get("tel", ""))
    poi_short = short_name_from_amap(poi.get("name", ""))
    poi_addr = norm_addr(poi.get("address", ""))

    if poi_phone and len(poi_phone) >= 8:
        for o in officials:
            if normalize_phone(o.get("phone", "")) == poi_phone:
                return o, "phone"

    if poi_short and len(poi_short) >= 2:
        exact_hits, prefix_hits = [], []
        for o in officials:
            on = (o.get("name") or "").strip()
            if on == poi_short:
                exact_hits.append(o)
            elif on.startswith(poi_short) or on.endswith(poi_short):
                prefix_hits.append(o)
        if len(exact_hits) == 1:
            return exact_hits[0], "name_exact"
        if len(exact_hits) > 1:
            for o in exact_hits:
                if addr_similarity(norm_addr(o.get("address", "")), poi_addr) > 0.5:
                    return o, "name_exact+addr"
            return exact_hits[0], "name_exact_multi"
        if len(prefix_hits) == 1:
            return prefix_hits[0], "name_prefix"

    best, best_score = None, 0.0
    for o in officials:
        s = addr_similarity(norm_addr(o.get("address", "")), poi_addr)
        if s > best_score:
            best_score, best = s, o
    if best and best_score >= 0.85:
        return best, f"addr({best_score:.2f})"

    return None, ""


def main():
    stations_doc = json.loads((DATA / "stations.json").read_text(encoding="utf-8"))
    officials_doc = json.loads((DATA / "sinopec_official_44.json").read_text(encoding="utf-8"))
    overrides = json.loads((DATA / "manual_overrides.json").read_text(encoding="utf-8")) \
        if (DATA / "manual_overrides.json").exists() else {}

    stations = stations_doc["stations"]
    officials = officials_doc["stations"]
    print(f"[Load] POI: {len(stations)} 座；官方售卡名单: {len(officials)} 座；"
          f"manual_overrides: {len(overrides)} 条")

    # 提取用户按"官方名单核验"标记的白名单 ID（唯一 confirmed 来源）
    whitelist = set(pid for pid, v in overrides.items()
                    if v.get("status") == "confirmed")
    unlikely_ids = set(pid for pid, v in overrides.items()
                       if v.get("status") == "unlikely")
    print(f"[Whitelist] 官方名单核验 confirmed: {len(whitelist)} 座；"
          f"用户标记 unlikely: {len(unlikely_ids)} 座")

    stats = {"matched": 0, "unmatched": 0,
             "by_phone": 0, "by_name_exact": 0, "by_name_prefix": 0, "by_addr": 0,
             "confirmed_from_whitelist": 0,
             "kept_unlikely_user": 0, "downgraded_jv_marker": 0,
             "kept_unverified": 0}

    for s in stations:
        sid = s["id"]
        o, method = find_match(s, officials)

        # ---- 售卡站字段（后台核查用，不影响 status） ----
        if o:
            s["has_card_network"] = True
            s["card_network_match_method"] = method
            s["official_station_name"] = o.get("name", "")
            s["official_address"] = o.get("address", "")
            s["official_phone"] = o.get("phone", "")
            stats["matched"] += 1
            if method.startswith("phone"):
                stats["by_phone"] += 1
            elif method.startswith("name_exact"):
                stats["by_name_exact"] += 1
            elif method == "name_prefix":
                stats["by_name_prefix"] += 1
            elif method.startswith("addr"):
                stats["by_addr"] += 1
        else:
            s["has_card_network"] = False
            s["card_network_match_method"] = ""
            s["official_station_name"] = ""
            s["official_address"] = ""
            s["official_phone"] = ""
            stats["unmatched"] += 1

        # ---- status 由白名单/用户标记驱动，售卡站匹配不升级 ----
        if sid in whitelist:
            s["status"] = "confirmed"
            s["hint"] = "官方名单核验：中石化深圳分公司官方名单确认，参与爱跑98优惠。"
            stats["confirmed_from_whitelist"] += 1
        elif sid in unlikely_ids:
            s["status"] = "unlikely"
            s["hint"] = overrides[sid].get("note", "用户人工标记不参与")
            stats["kept_unlikely_user"] += 1
        elif any(m in s.get("name", "") or m in s.get("address", "") for m in JV_MARKERS):
            s["status"] = "unlikely"
            s["hint"] = "名称/地址含合资特征（碧辟/联合/联营等），活动限自营站。"
            stats["downgraded_jv_marker"] += 1
        else:
            s["status"] = "unverified"
            if s["has_card_network"]:
                s["hint"] = "售卡站自动匹配成功（后台交叉核查用）；尚未人工核实是否有爱跑98。"
            else:
                s["hint"] = "未在售卡站自动匹配中命中；爱跑98销售情况待人工核实。"
            stats["kept_unverified"] += 1

    # ---- 更新 meta ----
    c = Counter(s["status"] for s in stations)
    stations_doc["meta"]["updated"] = "2026-09-24"
    stations_doc["meta"]["statusMeaning"] = {
        "confirmed": "已核实：官方名单核验参与爱跑98优惠的自营站",
        "unverified": "待核实：中石化站点（售卡站字段仅供后台交叉核查，不改变状态）",
        "unlikely": "疑似不参与：名称含合资特征或用户人工标记不参与",
    }
    stations_doc["meta"]["note"] = ("前台仅展示 confirmed（默认）；其余状态可在筛选里查看。"
                                    "售卡站数据保留在 has_card_network 字段，供后续交叉核查。")
    stations_doc["meta"]["counts_by_status"] = dict(c)
    stations_doc["meta"]["official_source"] = "sinopecsales.com 加油站网点查询（广东全省售卡站，仅后台核查用）"
    stations_doc["meta"]["confirmed_source"] = "data/manual_overrides.json（中石化深圳分公司官方名单核验，61 座）"

    (DATA / "stations.json").write_text(
        json.dumps(stations_doc, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 报告 ----
    lines = [
        "=== 收窄后匹配报告 ===",
        f"POI 站点: {len(stations)}",
        f"售卡站名单: {len(officials)}",
        "",
        "售卡站自动匹配（仅写入后台字段，不改 status）:",
        f"  命中售卡站:  {stats['matched']:>4} 座  "
        f"(phone {stats['by_phone']} / name {stats['by_name_exact']} / "
        f"prefix {stats['by_name_prefix']} / addr {stats['by_addr']})",
        f"  未命中:      {stats['unmatched']:>4} 座",
        "",
        "status 分布（唯一来源：manual_overrides.json 白名单）:",
        f"  confirmed（白名单官方核验）:   {stats['confirmed_from_whitelist']:>4}",
        f"  unlikely（用户人工标记）:       {stats['kept_unlikely_user']:>4}",
        f"  unlikely（名称/地址含合资特征）:{stats['downgraded_jv_marker']:>4}",
        f"  unverified（默认）:             {stats['kept_unverified']:>4}",
    ]
    report = "\n".join(lines)
    (DATA / "match_report.txt").write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"\n最终 status 分布: {dict(c)}")

    # 关键校验
    print("\n关键校验：")
    for s in stations:
        n = s.get("name", "")
        if "彩田" in n or "南坪" in n:
            print(f"  {n} | status={s['status']} | has_card_network={s.get('has_card_network')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
