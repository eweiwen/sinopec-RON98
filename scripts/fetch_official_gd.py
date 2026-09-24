# -*- coding: utf-8 -*-
"""
抓取中石化加油卡网上营业厅「加油站网点查询」广东全省数据。
数据源：https://www.sinopecsales.com/website/gasStationAction_queryGasStationByCondition.action
接口无需登录、无需 Token，纯公开 GET。

用法：
    python fetch_official_gd.py                          # 抓全部 92 页
    python fetch_official_gd.py --province 44            # 指定省（默认 44=广东）
    python fetch_official_gd.py --province 44 --max 5    # 只抓前 5 页（调试用）

输出：
    data/sinopec_official_<province>.json
    字段：serial, name, address, card_charge, phone, e_invoice, vat_invoice, page
"""
import json
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
URL_TMPL = "https://www.sinopecsales.com/website/gasStationAction_queryGasStationByCondition.action?{qs}"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ROW_RE = re.compile(
    r'<tr height="35px"[^>]*>.*?'
    r'<td[^>]*>\s*(\d+)\s*</td>\s*'       # 序号
    r'<td[^>]*>\s*([^<]*?)\s*</td>\s*'   # 网点名称
    r'<td[^>]*>\s*([^<]*?)\s*</td>\s*'   # 地址
    r'<td[^>]*>\s*([^<]*?)\s*</td>\s*'   # 售卡充值
    r'<td[^>]*>\s*([^<]*?)\s*</td>\s*'   # 电话
    r'<td[^>]*>\s*([^<]*?)\s*</td>\s*'   # 电子充值卡发票
    r'<td[^>]*>\s*([^<]*?)\s*</td>\s*'   # 增值税发票
    r'</tr>',
    re.DOTALL,
)
TOTAL_PAGE_RE = re.compile(r"var\s+totalPage\s*=\s*'(\d+)'")


def fetch_page(province: str, page_no: int, ua: str = UA) -> tuple[dict, list[dict]]:
    qs = urllib.parse.urlencode({
        "province": province,
        "page.pageNo": page_no,
        "stationCharge": 2,       # 全部
    })
    req = urllib.request.Request(URL_TMPL.format(qs=qs), headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=20) as resp:
        # 该站点固定返回 GBK 编码（Content-Type: text/html;charset=gbk）
        charset = resp.headers.get_content_charset() or "gbk"
        html = resp.read().decode(charset, errors="replace")

    total_m = TOTAL_PAGE_RE.search(html)
    total_page = int(total_m.group(1)) if total_m else -1

    rows = []
    for m in ROW_RE.finditer(html):
        serial, name, address, card, phone, e_inv, vat = m.groups()
        def clean(s):
            return re.sub(r"\s+", " ", s).strip()
        rows.append({
            "serial": int(serial),
            "name": clean(name),
            "address": clean(address),
            "card_charge": clean(card) == "是",
            "phone": clean(phone),
            "e_invoice": clean(e_inv) == "是",
            "vat_invoice": clean(vat) == "是",
            "page": page_no,
        })
    return {"province": province, "page": page_no, "total_page": total_page}, rows


def main():
    province = "44"
    max_pages = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--province" and i + 1 < len(args):
            province = args[i + 1]
        elif a == "--max" and i + 1 < len(args):
            max_pages = int(args[i + 1])

    # 先抓第 1 页拿到 total_page
    meta, first_rows = fetch_page(province, 1)
    total_page = meta["total_page"]
    print(f"[{province}] 总页数：{total_page}（第1页解析到 {len(first_rows)} 行）")

    all_rows = list(first_rows)
    pages_to_fetch = range(2, total_page + 1) if max_pages is None else range(2, min(max_pages, total_page) + 1)
    for p in pages_to_fetch:
        try:
            meta, rows = fetch_page(province, p)
            print(f"  page {p:>3}/{total_page}: {len(rows)} rows")
            all_rows.extend(rows)
            time.sleep(0.4)  # 温和限速，避免触发风控
        except Exception as e:
            print(f"  page {p}: FAILED - {e}")

    out = DATA_DIR / f"sinopec_official_{province}.json"
    DATA_DIR.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "source": "https://www.sinopecsales.com/website/gasStationAction_queryGasStationByCondition.action",
        "province_code": province,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_page": total_page,
        "count": len(all_rows),
        "stations": all_rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOK: {out}  共 {len(all_rows)} 条")


if __name__ == "__main__":
    main()
