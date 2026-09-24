#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取广东省（指定区域）中国石化加油站 POI。
数据源：高德 Web 服务 API v3 place/text
坐标系：GCJ-02（火星坐标），可直接用于高德 JS API

采集策略：
  1) 城市级检索（city=<城市名>，types=010101 中国石化）
  2) 区级分片检索（city=<城市名>&keywords=<区名>），提高召回、避免深分页截断
  3) 按 POI id 去重后合并

注意：本脚本使用的 key 仅在本机运行，不写入仓库（仓库通过 GitHub Actions Secret 注入）。
"""
import json
import os
import time
import urllib.parse
import urllib.request
from collections import OrderedDict

# key 从环境变量或本地密钥文件读取，绝不写入仓库（安全设计）
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

# 目标区域：用户指定 7 市 + 汕尾（深汕特别合作区从汕尾市域内按坐标筛出）
CITIES = ["深圳", "珠海", "广州", "惠州", "东莞", "汕头", "肇庆", "汕尾"]

TYPECODE = "010101"  # 中国石化
PAGE_SIZE = 25       # v3 建议不超过 25
MAX_PAGE = 20        # 单条件最多翻 20 页（500 条），足够覆盖各区

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW_PATH = os.path.join(OUT_DIR, "raw_pois.json")


def request(params, retry=3):
    url = BASE + "?" + urllib.parse.urlencode(params, encoding="utf-8")
    for i in range(retry):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "1":
                return data
            info = data.get("info", "")
            # 配额/并发限制时退避重试
            if "CUQPS" in info or "DAILY" in info or "LIMIT" in info.upper():
                time.sleep(2 + i * 2)
                continue
            return data
        except Exception as e:
            time.sleep(1.5 + i)
    return {"status": "0", "info": "request failed", "pois": []}


def search(city, keywords="", page=1):
    params = OrderedDict([
        ("key", KEY),
        ("keywords", keywords),
        ("types", TYPECODE),
        ("city", city),
        ("citylimit", "true"),
        ("offset", str(PAGE_SIZE)),
        ("page", str(page)),
        ("output", "JSON"),
    ])
    return request(params)


def fetch_city(city):
    """城市级 + 区级双重采集"""
    pois = OrderedDict()
    districts = set()

    # 1) 城市级
    total = 0
    for page in range(1, MAX_PAGE + 1):
        data = search(city, "", page)
        if data.get("status") != "1":
            break
        if page == 1:
            total = int(data.get("count", 0) or 0)
            print(f"    [{city}] 城市级命中 {total} 条")
        batch = data.get("pois", []) or []
        if not batch:
            break
        for p in batch:
            pois[p["id"]] = p
            if p.get("adname"):
                districts.add(p["adname"])
        if len(batch) < PAGE_SIZE:
            break
        time.sleep(0.25)

    # 2) 区级分片（补充召回）
    for ad in sorted(districts):
        for page in range(1, MAX_PAGE + 1):
            data = search(city, ad, page)
            if data.get("status") != "1":
                break
            batch = data.get("pois", []) or []
            if not batch:
                break
            new = 0
            for p in batch:
                if p["id"] not in pois:
                    pois[p["id"]] = p
                    new += 1
            if len(batch) < PAGE_SIZE:
                break
            time.sleep(0.25)
        time.sleep(0.2)

    return list(pois.values()), sorted(districts)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    result = {}
    for city in CITIES:
        print(f"[采集] {city} ...")
        pois, districts = fetch_city(city)
        print(f"    去重后 {len(pois)} 条；行政区：{', '.join(districts)}")
        result[city] = pois
        time.sleep(0.3)

    with open(RAW_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    total = sum(len(v) for v in result.values())
    print(f"\n[完成] 合计 {total} 条，已写入 {RAW_PATH}")


if __name__ == "__main__":
    main()
