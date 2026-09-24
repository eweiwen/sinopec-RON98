# -*- coding: utf-8 -*-
"""
将「中石化加油卡网上营业厅·加油站网点查询」的广东官方名单
与高德 POI 抓取的 1008 座站点做三级匹配：
  1) 电话精确匹配（最强）
  2) 站名短名匹配（中等）
  3) 地址模糊匹配（辅助）

产出：
  data/stations.json  每座站增加：
    - official_verified: bool
    - official_source: "phone" | "name" | "address" | ""
    - official_station_name, official_address, official_phone: 官方字段回填
    - status: confirmed/unverified/unlikely（保留原人工标记优先级）
  data/match_report.txt  匹配诊断报告
"""
import json
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

AMAP_PREFIX_RE = re.compile(r"^(中国石化|中国石油化工|中石化|中石化)\s*")
AMAP_SUFFIX_RE = re.compile(r"(加油加气站|加气加油站|加油站|加气站|充电站|服务[区站]|加油站|站点)$")

# 广东地名前缀，用于地址归一化
CITY_PREFIX = ("广东省", "广州市", "深圳市", "珠海市", "惠州市", "东莞市", "中山市",
               "汕头市", "肇庆市", "汕尾市", "江门市", "佛山市", "湛江市", "清远市",
               "河源市", "梅州市", "潮州市", "揭阳市", "云浮市", "韶关市", "茂名市",
               "潮州市", "河源市", "茂名市", "阳江市", "清远市", "云浮市", "中山市")
DISTRICT_WORDS = re.compile(r"(市|区|县|镇|乡|街道)\s*")


def normalize_phone(p: str) -> str:
    """只留数字"""
    return re.sub(r"[^\d]", "", p or "")


def short_name_from_amap(name: str) -> str:
    """从 '中国石化光明加油站' 提取 '光明'"""
    n = AMAP_PREFIX_RE.sub("", name).strip()
    n = AMAP_SUFFIX_RE.sub("", n).strip()
    return n


def norm_addr(a: str) -> str:
    """去省市前缀、去空白，便于比较"""
    s = (a or "").strip()
    for p in CITY_PREFIX:
        if s.startswith(p):
            s = s[len(p):]
            break
    s = re.sub(r"[\s\u3000]+", "", s)
    return s


def addr_similarity(a: str, b: str) -> float:
    """两个归一化地址的相似比"""
    return SequenceMatcher(None, a, b).ratio()


def find_match(poi: dict, officials: list) -> tuple[dict | None, str]:
    """
    为高德 POI 在官方名单里找匹配。
    返回 (matched_official_record, match_method)。
    """
    poi_phone = normalize_phone(poi.get("tel", ""))
    poi_short = short_name_from_amap(poi.get("name", ""))
    poi_addr = norm_addr(poi.get("address", ""))

    # 1) 电话精确匹配
    if poi_phone and len(poi_phone) >= 8:
        for o in officials:
            if normalize_phone(o.get("phone", "")) == poi_phone:
                return o, "phone"

    # 2) 站名短名精确匹配（POI 短名 == 官方 name 或 官方 name 以 POI 短名开头）
    if poi_short and len(poi_short) >= 2:
        exact_hits = []
        prefix_hits = []
        for o in officials:
            on = o.get("name", "").strip()
            if on == poi_short:
                exact_hits.append(o)
            elif on.startswith(poi_short) or on.endswith(poi_short):
                prefix_hits.append(o)
        if len(exact_hits) == 1:
            return exact_hits[0], "name_exact"
        if len(exact_hits) > 1:
            # 多候选：用地址辅助
            for o in exact_hits:
                if addr_similarity(norm_addr(o.get("address", "")), poi_addr) > 0.5:
                    return o, "name_exact+addr"
            return exact_hits[0], "name_exact_multi"
        if len(prefix_hits) == 1:
            return prefix_hits[0], "name_prefix"

    # 3) 地址模糊匹配（≥0.85 视为同一站）
    best, best_score = None, 0.0
    for o in officials:
        s = addr_similarity(norm_addr(o.get("address", "")), poi_addr)
        if s > best_score:
            best_score = s
            best = o
    if best and best_score >= 0.85:
        return best, f"addr({best_score:.2f})"

    return None, ""


def main():
    sys.exit(__run())


def __run() -> int:
    stations_doc = json.loads((DATA / "stations.json").read_text(encoding="utf-8"))
    officials_doc = json.loads((DATA / "sinopec_official_44.json").read_text(encoding="utf-8"))

    stations = stations_doc["stations"]
    officials = officials_doc["stations"]
    print(f"[Load] Amap POI: {len(stations)} 座；官方名单: {len(officials)} 座")

    # 索引：官方侧
    by_phone = {}
    for o in officials:
        p = normalize_phone(o.get("phone", ""))
        if p:
            by_phone.setdefault(p, []).append(o)

    # JV / 加盟 特征关键词（名称或地址命中即降级）
    JV_MARKERS = ["碧辟", "联合石油", "中化", "联营", "合资", "壳牌", "中油碧辟"]

    # 逐站匹配
    stats = {"matched": 0, "unmatched": 0, "by_phone": 0, "by_name_exact": 0,
             "by_name_exact_multi": 0, "by_name_prefix": 0, "by_addr": 0,
             "upgraded_to_confirmed": 0, "kept_confirmed_user": 0,
             "kept_unlikely_user": 0, "kept_unverified": 0,
             "downgraded_jv_marker": 0}

    for s in stations:
        prev_status = s.get("status", "unverified")
        o, method = find_match(s, officials)
        if o:
            s["official_verified"] = True
            s["official_source"] = method
            s["official_station_name"] = o.get("name", "")
            s["official_address"] = o.get("address", "")
            s["official_phone"] = o.get("phone", "")
            stats["matched"] += 1
            if method.startswith("phone"):
                stats["by_phone"] += 1
            elif method.startswith("name_exact"):
                stats["by_name_exact"] += 1
                if "multi" in method:
                    stats["by_name_exact_multi"] += 1
            elif method == "name_prefix":
                stats["by_name_prefix"] += 1
            elif method.startswith("addr"):
                stats["by_addr"] += 1
            # 状态：官方命中 → confirmed（人工核验的 unlikely 例外保留）
            if prev_status == "unlikely":
                s["status"] = "unlikely"      # 人工判定优先
                s["hint"] = "用户人工标记：不参与。虽在官方售卡网名单内，但业务口径不参与爱跑98。"
                stats["kept_unlikely_user"] += 1
            else:
                s["status"] = "confirmed"
                if prev_status == "unverified":
                    stats["upgraded_to_confirmed"] += 1
                else:
                    stats["kept_confirmed_user"] += 1
        else:
            s["official_verified"] = False
            s["official_source"] = ""
            s["official_station_name"] = ""
            s["official_address"] = ""
            s["official_phone"] = ""
            stats["unmatched"] += 1
            # 官方名单未收录 → 但加油卡网点查询只是"售卡站"子集，不等于非自营
            if prev_status == "confirmed":
                # 用户人工核验过（如南坪），保留 confirmed 但标注
                s["hint"] = "用户人工核验确认参与活动；但未在中石化官方售卡网名单内（可能不在售卡网络或数据源缺口）。"
                stats["kept_confirmed_user"] += 1
            elif prev_status == "unlikely":
                # 用户人工标记不参与，保留
                stats["kept_unlikely_user"] += 1
            elif any(m in s.get("name", "") or m in s.get("address", "") for m in JV_MARKERS):
                # 名称/地址明显合资特征 → 降级
                s["status"] = "unlikely"
                s["hint"] = f"名称/地址含合资特征（如碧辟/联合/联营），未收录于官方售卡网。"
                stats["downgraded_jv_marker"] += 1
            else:
                # 保留 unverified，但明确记录未命中原因
                s["status"] = "unverified"
                s["hint"] = "未收录于中石化官方加油卡售卡网点名单，可能不在售卡网络；也可能是真实自营但数据源未覆盖。"
                stats["kept_unverified"] += 1

    # 写入
    stations_doc["meta"]["official_source"] = "sinopecsales.com 加油站网点查询（广东全省售卡站）"
    stations_doc["meta"]["updated"] = "2026-09-24"
    (DATA / "stations.json").write_text(
        json.dumps(stations_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    # 报告
    lines = [
        f"=== 官方名单匹配报告 ===",
        f"Amap POI 站点: {len(stations)}",
        f"官方名单站点: {len(officials)}",
        f"",
        f"匹配结果:",
        f"  命中官方名单:   {stats['matched']:>4} 座 ({stats['matched']/len(stations)*100:.1f}%)",
        f"    ├─ 电话精确匹配:          {stats['by_phone']:>4}",
        f"    ├─ 站名精确匹配:          {stats['by_name_exact']:>4}  (多候选 {stats['by_name_exact_multi']})",
        f"    ├─ 站名前后缀匹配:        {stats['by_name_prefix']:>4}",
        f"    └─ 地址模糊匹配:          {stats['by_addr']:>4}",
        f"  未命中:            {stats['unmatched']:>4} 座 ({stats['unmatched']/len(stations)*100:.1f}%)",
        f"",
        f"状态变更（用户人工标记优先级最高）:",
        f"  unverified → confirmed (官方命中):     {stats['upgraded_to_confirmed']:>4}",
        f"  confirmed 保持 (用户人工核验):        {stats['kept_confirmed_user']:>4}",
        f"  unlikely 保持 (用户人工标记):        {stats['kept_unlikely_user']:>4}",
        f"  unverified 保留 (未命中但无合资特征): {stats['kept_unverified']:>4}",
        f"  降级为 unlikely (含合资特征):         {stats['downgraded_jv_marker']:>4}",
    ]
    report = "\n".join(lines)
    (DATA / "match_report.txt").write_text(report, encoding="utf-8")
    print("\n" + report)

    # 状态分布
    from collections import Counter
    c = Counter(s["status"] for s in stations)
    print(f"\n状态分布: {dict(c)}")
    by_city = {}
    for s in stations:
        city = s.get("city", "?")
        by_city.setdefault(city, Counter())[s["status"]] += 1
    print("\n按城市分布:")
    for city, cnt in sorted(by_city.items(), key=lambda x: -sum(x[1].values())):
        print(f"  {city}: {dict(cnt)}")

    # 关键校验：彩田（用户确认是合资不参与）应该在 unmatched 里
    print("\n关键校验：")
    for s in stations:
        if "彩田" in s.get("name", ""):
            print(f"  [{s['city']}] {s['name']} -> status={s['status']}, official_verified={s['official_verified']}, hint={s.get('hint','')}")
        if "南坪" in s.get("name", ""):
            print(f"  [{s['city']}] {s['name']} -> status={s['status']}, official_verified={s['official_verified']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
