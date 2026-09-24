#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补抓：加油站全大类（types=010100，含加油加气站/其他品牌挂靠分类）
+ "加油加气站"关键词补充检索，过滤名称含"中国石化/中石化"的站点。
用途：修复 010101 子类漏收问题（如"中国石化南坪加油加气站"被归入其他分类）。
输出 data/raw_extra.json：{city:[poi,...]}（与 raw_pois.json 同结构）
"""
import json
import os
import time
import urllib.parse
import urllib.request
from collections import OrderedDict

import pathlib
def _load_key():
    k = os.environ.get("AMAP_KEY", "").strip()
    if k:
        return k
    f = pathlib.Path(__file__).parent / ".amap_key"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    raise SystemExit("未找到高德 key：请设置环境变量 AMAP_KEY 或创建 scripts/.amap_key")

KEY = _load_key()
BASE = "https://restapi.amap.com/v3/place/text"

CITIES = ["深圳", "珠海", "广州", "惠州", "东莞", "汕头", "肇庆", "汕尾"]
PAGE_SIZE = 25
MAX_PAGE = 40  # 全大类数量大（广州 1000+），需多页；配合区级分片提高召回

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW_PATH = os.path.join(OUT_DIR, "raw_extra.json")


def request(params, retry=3):
    url = BASE + "?" + urllib.parse.urlencode(params, encoding="utf-8")
    for i in range(retry):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "1":
                return data
            time.sleep(2 + i * 2)
        except Exception:
            time.sleep(1.5 + i)
    return {"status": "0", "info": "failed", "pois": []}


def is_sinopec_name(name: str) -> bool:
    return ("中国石化" in name) or ("中石化" in name)


def fetch_type(city, typecode, label):
    """按类型码抓取，城市级+区级双采集"""
    pois = OrderedDict()
    districts = set()
    for page in range(1, MAX_PAGE + 1):
        params = OrderedDict([
            ("key", KEY), ("keywords", ""), ("types", typecode),
            ("city", city), ("citylimit", "true"),
            ("offset", str(PAGE_SIZE)), ("page", str(page)), ("output", "JSON"),
        ])
        data = request(params)
        batch = data.get("pois", []) or []
        if page == 1:
            print(f"    [{city}|{label}] 命中 {data.get('count', 0)}")
        if not batch:
            break
        for p in batch:
            if is_sinopec_name(p.get("name") or ""):
                pois[p["id"]] = p
            if p.get("adname"):
                districts.add(p["adname"])
        if len(batch) < PAGE_SIZE:
            break
        time.sleep(0.25)
    for ad in sorted(districts):
        for page in range(1, MAX_PAGE + 1):
            params = OrderedDict([
                ("key", KEY), ("keywords", ad), ("types", typecode),
                ("city", city), ("citylimit", "true"),
                ("offset", str(PAGE_SIZE)), ("page", str(page)), ("output", "JSON"),
            ])
            data = request(params)
            batch = data.get("pois", []) or []
            if not batch:
                break
            for p in batch:
                if is_sinopec_name(p.get("name") or ""):
                    pois.setdefault(p["id"], p)
            if len(batch) < PAGE_SIZE:
                break
            time.sleep(0.25)
        time.sleep(0.2)
    return pois


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    result = {}
    for city in CITIES:
        print(f"[补抓] {city} ...")
        merged = fetch_type(city, "010100", "加油站大类")
        # 加油加气站关键词补充（可能归入其他一级分类）
        for page in range(1, 6):
            params = OrderedDict([
                ("key", KEY), ("keywords", "加油加气"), ("city", city),
                ("citylimit", "true"), ("offset", "25"), ("page", str(page)),
                ("output", "JSON"),
            ])
            data = request(params)
            batch = data.get("pois", []) or []
            if not batch:
                break
            for p in batch:
                if is_sinopec_name(p.get("name") or ""):
                    merged.setdefault(p["id"], p)
            if len(batch) < 25:
                break
            time.sleep(0.25)
        result[city] = list(merged.values())
        print(f"    合并后 {len(merged)} 座")
        time.sleep(0.3)

    with open(RAW_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    total = sum(len(v) for v in result.values())
    print(f"\n[完成] 补抓合计 {total} 座 -> {RAW_PATH}")


if __name__ == "__main__":
    main()
