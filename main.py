import json
import time
import signal
import sys
from datetime import datetime, date, time as dt_time

from collector import fetch_realtime
from analyzer import analyze_realtime, analyze_daily, format_summary
from notifier import create_notifiers
from storage import Storage


def load_config(path="config.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_trading_day():
    return datetime.now().weekday() < 5


def is_trading_time():
    t = datetime.now().time()
    return (dt_time(9, 25) <= t <= dt_time(11, 30)) or \
           (dt_time(13, 0) <= t <= dt_time(15, 1))


def should_run_daily(last_date):
    if not is_trading_day():
        return False
    today = date.today()
    if last_date == today:
        return False
    now = datetime.now().time()
    return dt_time(15, 5) <= now <= dt_time(15, 30)


def push_all(notifiers, title, body):
    for n in notifiers:
        try:
            n.send(title, body)
        except Exception as e:
            print(f"[main] 推送异常: {e}")


def main():
    config = load_config()
    watchlist = config.get("watchlist", {})
    interval = config.get("interval_seconds", 60)
    storage = Storage(config.get("database", "stock_monitor.db"))
    notifiers = create_notifiers(config.get("notifiers", {}))

    if not notifiers:
        print("[main] 警告: 未启用任何推送渠道")
        from notifier import ConsoleNotifier
        notifiers.append(ConsoleNotifier())

    print(f"[main] 启动股票监控，共 {len(watchlist)} 只股票")
    print(f"[main] 推送渠道: {[type(n).__name__ for n in notifiers]}")

    daily_done_date = None
    last_summary_min = -1
    running = True

    def handle_exit(sig, frame):
        nonlocal running
        print("\n[main] 收到退出信号，正在停止...")
        running = False

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    while running:
        now = datetime.now()

        try:
            # --- 收盘结算 ---
            if should_run_daily(daily_done_date):
                print(f"[main] {now} 执行收盘结算")
                msgs = analyze_daily(watchlist, storage, config)
                for msg in msgs:
                    push_all(notifiers, "📊 收盘总结", msg)
                daily_done_date = date.today()

            # --- 盘中轮询 ---
            if is_trading_day() and is_trading_time():
                daily_done_date = None

                data = fetch_realtime(watchlist)
                if not data:
                    print(f"[main] {now} 无实时数据，跳过")
                    time.sleep(interval)
                    continue

                print(f"[main] {now} 获取 {len(data)} 只股票数据")

                alerts = analyze_realtime(data, storage, config, watchlist)
                for alert in alerts:
                    push_all(notifiers, alert["title"], alert["body"])

                current_min = now.minute
                if current_min != last_summary_min and current_min % 30 < 1:
                    summary = format_summary(data, watchlist)
                    push_all(notifiers, "📊 盘中简报", summary)
                    last_summary_min = current_min

                time.sleep(interval)

            else:
                time.sleep(60)

        except KeyboardInterrupt:
            print("\n[main] 用户中断")
            break
        except Exception as e:
            print(f"[main] 未预期错误: {e}")
            time.sleep(10)

    print("[main] 已停止")


def run_once(config, storage, notifiers):
    watchlist = config.get("watchlist", {})
    now = datetime.now()

    if should_run_daily(None):
        print(f"[main] CI: 执行收盘结算")
        msgs = analyze_daily(watchlist, storage, config)
        for msg in msgs:
            push_all(notifiers, "收盘总结", msg)
        return

    if not (is_trading_day() and is_trading_time()):
        return

    print(f"[main] CI: 盘中轮询")
    data = fetch_realtime(watchlist)
    if not data:
        return

    alerts = analyze_realtime(data, storage, config, watchlist)
    for alert in alerts:
        push_all(notifiers, alert["title"], alert["body"])


if __name__ == "__main__":
    if "--once" in sys.argv:
        cfg = load_config()
        s = Storage(cfg.get("database", "stock_monitor.db"))
        n = create_notifiers(cfg.get("notifiers", {}))
        run_once(cfg, s, n)
    else:
        main()
