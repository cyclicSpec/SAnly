import requests
import pandas as pd
import numpy as np
from datetime import datetime, date

from collector import _sina_code


def _fetch_daily_klines(code, limit=120):
    prefix = _sina_code(code)
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0",
    }
    url = (
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"CN_MarketData.getKLineData?symbol={prefix}&scale=240&ma=no&datalen={limit}"
    )
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        rows = resp.json()
        if not rows or not isinstance(rows, list):
            return None
        records = []
        for r in rows:
            records.append({
                "date": r["day"],
                "open": float(r["open"]),
                "close": float(r["close"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "volume": float(r.get("volume", 0)),
                "amount": 0,
            })
        df = pd.DataFrame(records)
        df["change_pct"] = df["close"].pct_change() * 100
        return df
    except Exception as e:
        print(f"[analyzer] {code} K线获取失败: {e}")
        return None


def analyze_realtime(data, storage, config, watchlist):
    thresholds = config.get("alerts", {})
    change_thr = thresholds.get("price_change_pct", 3.0)
    vol_thr = thresholds.get("volume_ratio", 1.8)
    alerts = []

    for code, info in data.items():
        name = watchlist.get(code, code)
        price = info["price"]
        yclose = info["yclose"]
        if yclose == 0:
            continue

        change_pct = (price - yclose) / yclose * 100
        ts = f"{info['date']} {info['time']}"

        if abs(change_pct) >= change_thr:
            direction = "大涨" if change_pct > 0 else "大跌"
            level = "warning" if abs(change_pct) >= 5.0 else "info"
            alerts.append({
                "title": f"{'⚠️' if level=='warning' else '📈'} {name} {direction}",
                "body": (
                    f"**{name}**（{code}）\n\n"
                    f"现价：**{price:.2f}**\n"
                    f"涨跌幅：**{change_pct:+.2f}%**\n"
                    f"今开：{info['open']:.2f}　昨收：{yclose:.2f}\n"
                    f"最高：{info['high']:.2f}　最低：{info['low']:.2f}\n"
                    f"时间：{ts}"
                ),
                "code": code,
                "level": level,
            })
            storage.save_signal(ts, code, "price_change", level,
                                f"{name} {direction} {change_pct:+.2f}%")

        avg_vol = storage.get_avg_volume(code, 5)
        if avg_vol and avg_vol > 0:
            vol_ratio = info["volume"] / avg_vol
            if vol_ratio >= vol_thr:
                direction = "放量上涨" if change_pct >= 0 else "放量下跌"
                alerts.append({
                    "title": f"📊 {name} {direction}",
                    "body": (
                        f"**{name}**（{code}）\n\n"
                        f"现价：{price:.2f}（{change_pct:+.2f}%）\n"
                        f"当前量：{info['volume']:.0f}\n"
                        f"5日均量：{avg_vol:.0f}\n"
                        f"量比：**{vol_ratio:.1f}x**\n"
                        f"时间：{ts}"
                    ),
                    "code": code,
                    "level": "info",
                })
                storage.save_signal(ts, code, "volume_spike", "info",
                                    f"{name} {direction} {vol_ratio:.1f}x")

    return alerts


def analyze_daily(watchlist, storage, config):
    today = date.today().isoformat()
    limit = config.get("daily", {}).get("history_days", 120)
    messages = []

    for code, name in watchlist.items():
        df = _fetch_daily_klines(code, limit)
        if df is None or df.empty:
            continue

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)

        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        dif, dea, hist = _macd(close)
        rsi = _rsi(close, 14)
        k, d, j = _kdj(close, high, low)

        last = df.iloc[-1]
        change_raw = last.get("change_pct")
        change_val = float(change_raw) if pd.notna(change_raw) else 0.0
        change_str = f"{change_val:+.2f}%"

        latest = {
            "date": str(last["date"])[:10],
            "open": float(last["open"]),
            "close": float(last["close"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
            "volume": float(last["volume"]),
            "amount": float(last.get("amount", 0)),
            "ma5": _v(ma5, -1),
            "ma10": _v(ma10, -1),
            "ma20": _v(ma20, -1),
            "ma60": _v(ma60, -1),
            "macd_dif": _v(dif, -1),
            "macd_dea": _v(dea, -1),
            "macd_hist": _v(hist, -1),
            "rsi_14": _v(rsi, -1),
            "k": _v(k, -1),
            "d": _v(d, -1),
            "j": _v(j, -1),
        }
        storage.save_daily(code, latest)

        macd_signal = "金叉 ↑" if latest["macd_hist"] > 0 else "死叉 ↓" if latest["macd_hist"] < 0 else "平"
        rsi_v = latest["rsi_14"]
        rsi_status = "超买 🔴" if rsi_v > 70 else "超卖 🟢" if rsi_v < 30 else "中性"

        messages.append(
            f"### {name}（{code}）\n\n"
            f"收盘：**{latest['close']:.2f}**　涨幅：{change_str}\n\n"
            f"**均线**\n"
            f"MA5: {latest['ma5']:.2f}　MA10: {latest['ma10']:.2f}\n"
            f"MA20: {latest['ma20']:.2f}　MA60: {latest['ma60']:.2f}\n\n"
            f"**技术指标**\n"
            f"MACD: {macd_signal}（{latest['macd_hist']:+.2f}）\n"
            f"RSI(14): {rsi_v:.1f}（{rsi_status}）\n"
            f"KDJ: K={latest['k']:.1f} D={latest['d']:.1f} J={latest['j']:.1f}\n"
            f"—————————————"
        )

    if not messages:
        return []
    header = f"# 📊 收盘总结（{today}）\n\n"
    return [header + "\n".join(messages)]


def format_summary(data, watchlist):
    now = datetime.now()
    lines = [f"# 📊 盘中简报（{now.strftime('%H:%M')}）\n"]
    for code, info in data.items():
        name = watchlist.get(code, code)
        yclose = info["yclose"]
        change = (info["price"] - yclose) / yclose * 100 if yclose else 0
        emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
        lines.append(
            f"{emoji} **{name}**　{info['price']:.2f}　{change:+.2f}%\n"
            f"> 高 {info['high']:.2f}　低 {info['low']:.2f}\n"
        )
    return "\n".join(lines)


# --- internal helpers ---

def _v(series, idx):
    val = series.iloc[idx]
    return float(val) if pd.notna(val) else 0.0


def _macd(close):
    exp12 = close.ewm(span=12, adjust=False).mean()
    exp26 = close.ewm(span=26, adjust=False).mean()
    dif = exp12 - exp26
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = 2 * (dif - dea)
    return dif, dea, hist


def _rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(n).mean()
    avg_loss = loss.rolling(n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _kdj(close, high, low, n=9):
    low_n = low.rolling(n).min()
    high_n = high.rolling(n).max()
    rsv = (close - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()
    j = 3 * k - 2 * d
    return k, d, j
