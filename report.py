import json, sys, traceback
from datetime import datetime
import pandas as pd
from storage import Storage
from analyzer import analyze_daily


def fmt(v, d=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "\u2014"
    return f"{v:.{d}f}"


def build_html(data, signals):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cards = ""

    for item in data:
        c = item["close"]
        ch = item.get("change_pct") or 0
        cls = "up" if ch > 0 else "down" if ch < 0 else "flat"

        macd_cls = "up" if item.get("macd_hist", 0) > 0 else "down"
        macd_sig = "\u91d1\u53c9 \u2191" if item["macd_hist"] > 0 else "\u6b7b\u53c9 \u2193" if item["macd_hist"] < 0 else "\u5e73"

        rsi = item.get("rsi_14") or 50
        rsi_cls = "up" if rsi > 70 else "down" if rsi < 30 else "flat"
        rsi_st = "\u8d85\u4e70" if rsi > 70 else "\u8d85\u5356" if rsi < 30 else "\u4e2d\u6027"

        cards += f"""
<div class="card">
    <div class="card-header">
        <span class="stock-name">{item['name']}</span>
        <span class="stock-code">{item['code']}</span>
        <span class="stock-price {cls}">{fmt(c)}</span>
        <span class="stock-change {cls}">{fmt(ch, 2)}%</span>
    </div>
    <div class="card-body">
        <div class="indicator-group">
            <div class="indicator-label">\u5747\u7ebf</div>
            <table class="indicator-table">
                <tr><td>MA5</td><td class="num">{fmt(item.get('ma5'))}</td><td>MA10</td><td class="num">{fmt(item.get('ma10'))}</td></tr>
                <tr><td>MA20</td><td class="num">{fmt(item.get('ma20'))}</td><td>MA60</td><td class="num">{fmt(item.get('ma60'))}</td></tr>
            </table>
        </div>
        <div class="indicator-group">
            <div class="indicator-label">MACD <span class="tag {macd_cls}">{macd_sig}</span></div>
            <table class="indicator-table">
                <tr><td>DIF</td><td class="num">{fmt(item.get('macd_dif'))}</td><td>DEA</td><td class="num">{fmt(item.get('macd_dea'))}</td></tr>
                <tr><td>\u67f1</td><td class="num {macd_cls}">{fmt(item.get('macd_hist'))}</td><td></td><td></td></tr>
            </table>
        </div>
        <div class="indicator-group">
            <div class="indicator-label">RSI(14) <span class="tag {rsi_cls}">{rsi_st}</span></div>
            <div class="rsi-bar"><div class="rsi-fill {rsi_cls}" style="width:{rsi}%"></div></div>
            <div class="rsi-label">{fmt(rsi, 1)}</div>
        </div>
        <div class="indicator-group">
            <div class="indicator-label">KDJ</div>
            <table class="indicator-table">
                <tr><td>K</td><td class="num">{fmt(item.get('k'))}</td><td>D</td><td class="num">{fmt(item.get('d'))}</td></tr>
                <tr><td>J</td><td class="num">{fmt(item.get('j'))}</td><td></td><td></td></tr>
            </table>
        </div>
    </div>
</div>"""

    sig_rows = ""
    for ts, code, typ, level, detail in signals:
        lvl_cls = "warn" if level == "warning" else "info"
        sig_rows += f"<tr><td>{ts}</td><td>{code}</td><td>{typ}</td><td class={lvl_cls}>{level}</td><td>{detail}</td></tr>"
    if not sig_rows:
        sig_rows = '<tr><td colspan="5" class="empty">\u6682\u65e0\u4fe1\u53f7\u8bb0\u5f55</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stock Monitor</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,'Segoe UI',sans-serif; background:#0d1117; color:#c9d1d9; padding:20px; }}
.header {{ max-width:1200px; margin:0 auto 24px; }}
.header h1 {{ font-size:24px; color:#f0f6fc; }}
.header .time {{ color:#8b949e; font-size:14px; margin-top:4px; }}
.grid {{ max-width:1200px; margin:0 auto; display:grid; grid-template-columns:repeat(auto-fill,minmax(380px,1fr)); gap:16px; }}
.card {{ background:#161b22; border:1px solid #30363d; border-radius:8px; overflow:hidden; }}
.card-header {{ display:flex; align-items:center; gap:12px; padding:12px 16px; background:#1c2128; border-bottom:1px solid #30363d; }}
.stock-name {{ font-size:16px; font-weight:600; color:#f0f6fc; }}
.stock-code {{ font-size:12px; color:#8b949e; }}
.stock-price {{ margin-left:auto; font-size:20px; font-weight:700; }}
.stock-change {{ font-size:14px; font-weight:600; min-width:70px; text-align:right; }}
.up {{ color:#3fb950; }}
.down {{ color:#f85149; }}
.flat {{ color:#8b949e; }}
.card-body {{ padding:12px 16px; }}
.indicator-group {{ margin-bottom:12px; }}
.indicator-group:last-child {{ margin-bottom:0; }}
.indicator-label {{ font-size:13px; color:#8b949e; margin-bottom:4px; }}
.indicator-table {{ width:100%; font-size:13px; }}
.indicator-table td {{ padding:2px 4px; color:#c9d1d9; }}
.indicator-table td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.tag {{ display:inline-block; font-size:11px; padding:1px 6px; border-radius:4px; margin-left:6px; }}
.tag.up {{ background:#0b2e1a; color:#3fb950; }}
.tag.down {{ background:#2d0f13; color:#f85149; }}
.rsi-bar {{ height:6px; background:#30363d; border-radius:3px; margin:4px 0; }}
.rsi-fill {{ height:100%; border-radius:3px; }}
.rsi-fill.up {{ background:#3fb950; }}
.rsi-fill.down {{ background:#f85149; }}
.rsi-fill.flat {{ background:#8b949e; }}
.rsi-label {{ font-size:12px; color:#8b949e; }}
.section {{ max-width:1200px; margin:24px auto 0; }}
.section h2 {{ font-size:18px; color:#f0f6fc; margin-bottom:12px; }}
.sig-table {{ width:100%; border-collapse:collapse; font-size:13px; background:#161b22; border:1px solid #30363d; border-radius:8px; overflow:hidden; }}
.sig-table th {{ background:#1c2128; color:#8b949e; font-weight:500; padding:10px 12px; text-align:left; border-bottom:1px solid #30363d; }}
.sig-table td {{ padding:8px 12px; border-bottom:1px solid #21262d; color:#c9d1d9; }}
.sig-table td.warn {{ color:#f85149; }}
.sig-table td.info {{ color:#58a6ff; }}
.sig-table td.empty {{ text-align:center; color:#484f58; padding:20px; }}
.footer {{ max-width:1200px; margin:24px auto 0; text-align:center; color:#484f58; font-size:12px; }}
</style>
</head>
<body>
<div class="header">
    <h1>Stock Monitor</h1>
    <div class="time">\u66f4\u65b0\u4e8e {now}</div>
</div>
<div class="grid">{cards}</div>
<div class="section">
    <h2>\u4fe1\u53f7\u8bb0\u5f55</h2>
    <table class="sig-table">
        <thead><tr><th>\u65f6\u95f4</th><th>\u4ee3\u7801</th><th>\u7c7b\u578b</th><th>\u7ea7\u522b</th><th>\u8be6\u60c5</th></tr></thead>
        <tbody>{sig_rows}</tbody>
    </table>
</div>
<div class="footer">\u6570\u636e\u6765\u6e90\uff1a\u65b0\u6d6a\u8d22\u7ecf | Stock Monitor v1</div>
</body>
</html>"""
    return html


def main():
    config = json.load(open("config.json", encoding="utf-8"))
    watchlist = config.get("watchlist", {})
    s = Storage(config.get("database", "stock_monitor.db"))

    has_data = any(s.get_latest_daily(code) for code in watchlist)
    if not has_data:
        print("DB empty, running daily analysis...")
        analyze_daily(watchlist, s, config)

    data = []
    for code, name in watchlist.items():
        d = s.get_latest_daily(code)
        if d:
            d["name"] = name
            d["code"] = code
            data.append(d)

    signals = s.get_recent_signals(20)
    html = build_html(data, signals)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html generated: {len(data)} stocks, {len(signals)} signals")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        print(err, flush=True)
        # generate error page
        html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Stock Monitor - Error</title></head>
<body style="background:#0d1117;color:#c9d1d9;padding:40px;font-family:sans-serif;">
<h1>Error</h1>
<pre style="color:#f85149;">{err}</pre>
</body>
</html>"""
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)
        sys.exit(1)
