#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析官方名单 OCR 文本 -> 与 stations.json 匹配 -> 输出 manual_overrides 增量

匹配策略（站名简称为 OCR 主体，地址做交叉验证）：
  1) 站库中 name 含简称（如"北环"→"中国石化北环加油站"），同城市限定深圳；
  2) 命中多个时用地址包含关系消歧（OCR 地址片段 vs 库内地址）；
  3) 仍多命中/零命中 -> 输出到未匹配报告，不自动标注。

输出：
  data/official_sz_list.json   解析后的官方名单（61行）
  控制台报告：matched / ambiguous / unmatched
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW_TXT = os.path.join(DATA, "official_sz_list_raw.txt")

DISTRICTS = ["福田", "罗湖", "南山", "盐田", "宝安", "龙岗", "龙华", "坪山", "光明", "大鹏"]


def parse_ocr():
    lines = [l.strip() for l in open(RAW_TXT, encoding="utf-8") if l.strip()]
    rows = []
    i = 0
    cur = None
    while i < len(lines):
        l = lines[i]
        if re.fullmatch(r"\d{1,2}", l):  # 序号行
            if cur:
                rows.append(cur)
            cur = {"no": int(l), "district": "", "name": "", "addr": ""}
        elif cur is not None:
            if l in DISTRICTS and not cur["district"]:
                cur["district"] = l
            elif not cur["name"] and "区" not in l[:4] and len(l) <= 8:
                cur["name"] = l
            elif l.startswith(("更多惊喜", "公众号", "欢迎")):
                if cur:
                    rows.append(cur); cur = None
                break
            elif not cur["addr"]:
                cur["addr"] = l
            elif cur["addr"] and len(l) > len(cur["addr"]):
                cur["addr"] = l  # 地址被拆行时取长者
        i += 1
    if cur:
        rows.append(cur)
    return rows


def norm_addr(a):
    a = re.sub(r"[（(].*?[)）]", "", a or "")
    return re.sub(r"[^\u4e00-\u9fa50-9]", "", a)


def main():
    rows = parse_ocr()
    print(f"OCR 解析出 {len(rows)} 行")
    stations = json.load(open(os.path.join(DATA, "stations.json"), encoding="utf-8"))["stations"]
    sz = [s for s in stations if s["city"] == "深圳"]

    matched, ambiguous, unmatched = {}, [], []
    for r in rows:
        kw = r["name"]
        if not kw:
            unmatched.append(r); continue
        cand = [s for s in sz if kw in s["name"]]
        if len(cand) > 1 and r["addr"]:
            na = norm_addr(r["addr"])
            narrowed = [s for s in cand if na and (na[:6] in norm_addr(s["address"]) or norm_addr(s["address"])[:6] in na)]
            if narrowed:
                cand = narrowed
        if len(cand) == 1:
            matched[cand[0]["id"]] = {
                "status": "confirmed",
                "note": f"官方名单核验（中石化深圳分公司，序号{r['no']}，{r['district']}·{kw}）",
            }
        elif len(cand) == 0:
            unmatched.append(r)
        else:
            ambiguous.append({"row": r, "cands": [s["name"] + "|" + s["address"] for s in cand[:4]]})

    # 写 overrides（保留既有彩田条目）
    ov_path = os.path.join(DATA, "manual_overrides.json")
    old = json.load(open(ov_path, encoding="utf-8")) if os.path.exists(ov_path) else {}
    old.update(matched)
    json.dump(old, open(ov_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(rows, open(os.path.join(DATA, "official_sz_list.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"\n[匹配结果] 已核实 {len(matched)} / 众多候选 {len(ambiguous)} / 未匹配 {len(unmatched)}")
    if ambiguous:
        print("\n== 多候选（需人工定夺）==")
        for x in ambiguous:
            print(f"  #{x['row']['no']} {x['row']['district']}·{x['row']['name']} -> {'；'.join(x['cands'])}")
    if unmatched:
        print("\n== 未匹配（站库中无对应站点）==")
        for r in unmatched:
            print(f"  #{r['no']} {r['district']}·{r['name']} | {r['addr']}")


if __name__ == "__main__":
    main()
