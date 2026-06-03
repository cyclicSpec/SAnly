import os
from abc import ABC, abstractmethod
import requests


class Notifier(ABC):
    @abstractmethod
    def send(self, title, body):
        pass


class ConsoleNotifier(Notifier):
    def send(self, title, body):
        sep = "=" * 40
        print(f"\n{sep}")
        print(title)
        print("-" * 40)
        print(body)
        print(f"{sep}\n")


class DingTalkNotifier(Notifier):
    def __init__(self, webhook):
        self.webhook = webhook

    def send(self, title, body):
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": body},
        }
        try:
            resp = requests.post(self.webhook, json=payload, timeout=10)
            if resp.status_code != 200:
                print(f"[dingtalk] 推送失败: {resp.text}")
        except requests.RequestException as e:
            print(f"[dingtalk] 请求异常: {e}")


class WeComNotifier(Notifier):
    def __init__(self, webhook):
        self.webhook = webhook

    def send(self, title, body):
        markdown_content = body.replace("\n", "\n> ")
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": f"# {title}\n> {markdown_content}"},
        }
        try:
            resp = requests.post(self.webhook, json=payload, timeout=10)
            if resp.status_code != 200:
                print(f"[wecom] 推送失败: {resp.text}")
        except requests.RequestException as e:
            print(f"[wecom] 请求异常: {e}")


def create_notifiers(config):
    notifiers = []
    if config.get("console", {}).get("enabled", False):
        notifiers.append(ConsoleNotifier())

    dt_webhook = os.environ.get("DINGTALK_WEBHOOK") or config.get("dingtalk", {}).get("webhook")
    dt_enabled = config.get("dingtalk", {}).get("enabled", False) or bool(os.environ.get("DINGTALK_WEBHOOK"))
    if dt_enabled and dt_webhook:
        notifiers.append(DingTalkNotifier(dt_webhook))

    wc_webhook = os.environ.get("WECOM_WEBHOOK") or config.get("wecom", {}).get("webhook")
    wc_enabled = config.get("wecom", {}).get("enabled", False) or bool(os.environ.get("WECOM_WEBHOOK"))
    if wc_enabled and wc_webhook:
        notifiers.append(WeComNotifier(wc_webhook))

    return notifiers
