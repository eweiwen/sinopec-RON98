#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
以"爱跑98"为关键词，在各目标城市内检索高德 POI。
命中的站点（名称/别名/地址带"爱跑98"）可作为"该站销售爱跑98汽油"的强证据，
用于把对应站点标记为"已核实"。
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

CITIES = ["深圳", "珠海", "广州", "惠州", "东莞", "汕头", "肇庆", "汕尾"]
KEYWORDS = ["爱跑98", "爱跑 98", "RON98", "98号汽油"]

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW_PATH = os.path.join(OUT_DIR, "raw_aipao_hits.json")


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
    return {"status": "0", "info": "request failed", "pois": []}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    hits = OrderedDict()
    for city in CITIES:
        for kw in KEYWORDS:
            params = OrderedDict([
                ("key", KEY), ("keywords", kw), ("city", city),
                ("citylimit", "true"), ("offset", "25"), ("page", "1"),
                ("output", "JSON"),
            ])
            data = request(params)
            pois = data.get("pois", []) or []
            if pois:
                print(f"[{city}] kw={kw!r} 命中 {len(pois)}")
            for p in pois:
                # 只要加油站类
                if "加油" in (p.get("type") or "") or "加油站" in (p.get("name") or ""):
                    hits[p["id"]] = p
            time.sleep(0.3)

    with open(RAW_PATH, "w", encoding="utf-8") as f:
        json.dump(hits, f, ensure_ascii=False, indent=1)
    print(f"\n[完成] 爱跑98相关 POI 合计 {len(hits)} 条 -> {RAW_PATH}")


if __name__ == "__main__":
    main()
