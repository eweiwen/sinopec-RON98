#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据更新管线入口：抓 POI -> 抓爱跑98命中 -> 清洗输出 stations.json

用法（本机执行，key 不入仓库）：
  方式一：set AMAP_KEY=<你的高德key> && python run_all.py
  方式二：把 key 写入 scripts/.amap_key 文件（已被 .gitignore 排除）

更新流程：重跑本脚本 -> 核对 data/stations.json 变更 -> 提交推送 -> Pages 自动重新部署。
人工核验某站后：直接编辑 data/stations.json 中该站的 status 字段
  （confirmed / unverified / unlikely），无需重跑抓取。
"""
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))

for script in ("fetch_pois.py", "fetch_aipao_hits.py", "build_stations.py"):
    print(f"===== {script} =====")
    r = subprocess.run([sys.executable, os.path.join(HERE, script)])
    if r.returncode != 0:
        sys.exit(f"{script} 执行失败，管线中止")
print("全部完成。请检查 data/stations.json 并提交。")
