import json, sys, os, traceback
from datetime import datetime, date, time as dt_time
import pandas as pd
from storage import Storage
from collector import fetch_realtime
from analyzer import analyze_realtime, analyze_daily, _fetch_daily_klines
from notifier import create_notifiers


def fmt(v, d=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "\u2014"
    return f"{v:.{d}f}"


def build_html(stocks, now_str):
    cards = ""
    for s in stocks:
        c = s["price"]
        ch = s.get("change_pct", 0)
        cls = "up" if ch > 0 else "down" if ch < 0 else "flat"
        n = s.get("name", s["code"])

        ma5 = fmt(s.get("ma5"))
        ma10 = fmt(s.get("ma10"))
        ma20 = fmt(s.get("ma20"))
        ma60 = fmt(s.get("ma60"))
        rsi = s.get("rsi_14")
        rsi_str = fmt(rsi, 1) if rsi else "\u2014"
        rsi_st = "\u8d85\u4e70" if rsi and rsi > 70 else "\u8d85\u5356" if rsi and rsi < 30 else ""
        macd_h = s.get("macd_hist")
        macd_s = f"{'<span class=tag-up>\u91d1\u53c9 \u2191</span>' if macd_h and macd_h > 0 else '<span class=tag-down>\u6b7b\u53c9 \u2193</span>' if macd_h and macd_h < 0 else ''}"
        m5 = f"MA5 {ma5}" if ma5 != "\u2014" else ""
        m10 = f"MA10 {ma10}" if ma10 != "\u2014" else ""
        m20 = f"MA20 {ma20}" if ma20 != "\u2014" else ""
        m60 = f"MA60 {ma60}" if ma60 != "\u2014" else ""

        cards += f"""
<div class="card">
  <div class="card-h">
    <span class="name">{n}</span>
    <span class="code">{s['code']}</span>
    <span class="price {cls}">{fmt(c)}</span>
    <span class="chg {cls}">{ch:+.2f}%</span>
  </div>
  <div class="card-b">
    <div class="info">H {fmt(s['high'])} L {fmt(s['low'])} O {fmt(s['open'])}</div>
    <div class="ma">{m5} {m10}</div>
    <div class="ma">{m20} {m60}</div>
    <div class="info">RSI {rsi_str} {rsi_st} {macd_s}</div>
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="60">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stock Monitor</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#c9d1d9;font-family:-apple-system,sans-serif;padding:16px}}
.hdr{{margin-bottom:16px}}
.hdr h1{{font-size:20px;color:#f0f6fc}}
.hdr .time{{font-size:13px;color:#8b949e;margin-top:4px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;overflow:hidden}}
.card-h{{display:flex;align-items:center;gap:10px;padding:10px 14px;background:#1c2128;border-bottom:1px solid #30363d;font-size:14px}}
.name{{font-weight:600;color:#f0f6fc}}
.code{{color:#8b949e;font-size:12px}}
.price{{margin-left:auto;font-size:18px;font-weight:700}}
.chg{{font-weight:600;min-width:70px;text-align:right}}
.up{{color:#3fb950}}
.down{{color:#f85149}}
.flat{{color:#8b949e}}
.card-b{{padding:10px 14px;font-size:13px}}
.card-b .info{{color:#8b949e;margin-bottom:4px}}
.card-b .ma{{color:#c9d1d9;margin-bottom:4px;font-variant-numeric:tabular-nums}}
.tag-up{{color:#3fb950;font-size:12px}}
.tag-down{{color:#f85149;font-size:12px}}
.ftr{{text-align:center;color:#484f58;font-size:12px;margin-top:20px}}
</style>
</head>
<body>
<div class="hdr">
  <h1>Stock Monitor</h1>
  <div class="time">{now_str}</div>
</div>
<div class="grid">{cards}</div>
<div class="ftr">\u6bcf 60s \u81ea\u52a8\u5237\u65b0</div>
</body>
</html>"""


def main():
    config = json.load(open("config.json", encoding="utf-8"))
    watchlist = config.get("watchlist", {})
    s = Storage(config.get("database", "stock_monitor.db"))
    notifiers = create_notifiers(config.get("notifiers", {}))

    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    is_weekday = now.weekday() < 5
    t = now.time()

    # daily settlement at 15:05-15:30
    if is_weekday and dt_time(15, 5) <= t <= dt_time(15, 30):
        print("daily settlement...")
        msgs = analyze_daily(watchlist, s, config)
        for msg in msgs:
            for n in notifiers:
                n.send("收盘总结", msg)
        data = _fetch_merged(s, watchlist, realtime=False)
        push_alerts = []
    else:
        data = fetch_realtime(watchlist)
        if not data:
            print("no realtime data")
            data = _fetch_merged(s, watchlist, realtime=False)
        else:
            alerts = analyze_realtime(data, s, config, watchlist)
            for a in alerts:
                for n in notifiers:
                    n.send(a["title"], a["body"])
            data = _fetch_merged(s, watchlist, realtime=True, rt=data)

    if not data:
        print("no data at all")
        data = [{"code": k, "name": v, "price": 0, "change_pct": 0,
                 "high": 0, "low": 0, "open": 0} for k, v in watchlist.items()]

    html = build_html(data, now_str)
    os.makedirs("_site", exist_ok=True)
    with open("_site/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html generated: {len(data)} stocks")


def _fetch_merged(storage, watchlist, realtime=False, rt=None):
    results = []
    for code, name in watchlist.items():
        d = storage.get_latest_daily(code)
        if realtime and rt and code in rt:
            r = rt[code]
            item = {
                "code": code, "name": name,
                "price": r["price"], "high": r["high"], "low": r["low"], "open": r["open"],
                "change_pct": (r["price"] - r["yclose"]) / r["yclose"] * 100 if r["yclose"] else 0,
            }
            if d:
                item["ma5"] = d["ma5"]
                item["ma10"] = d["ma10"]
                item["ma20"] = d["ma20"]
                item["ma60"] = d["ma60"]
                item["rsi_14"] = d["rsi_14"]
                item["macd_hist"] = d["macd_hist"]
            results.append(item)
        elif d:
            results.append({
                "code": code, "name": name,
                "price": d["close"], "high": d["high"], "low": d["low"], "open": d["open"],
                "change_pct": 0,
                "ma5": d["ma5"], "ma10": d["ma10"], "ma20": d["ma20"], "ma60": d["ma60"],
                "rsi_14": d["rsi_14"], "macd_hist": d["macd_hist"],
            })
    return results


if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        print(err, flush=True)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta http-equiv="refresh" content="60"><title>Error</title></head>
<body style="background:#0d1117;color:#c9d1d9;padding:40px;font-family:sans-serif;"><h1>Error</h1><pre style="color:#f85149;">{err}</pre></body>
</html>"""
        os.makedirs("_site", exist_ok=True)
        with open("_site/index.html", "w", encoding="utf-8") as f:
            f.write(html)
        sys.exit(1)
