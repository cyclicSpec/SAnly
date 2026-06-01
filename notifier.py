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
    dt = config.get("dingtalk", {})
    if dt.get("enabled", False) and dt.get("webhook"):
        notifiers.append(DingTalkNotifier(dt["webhook"]))
    wc = config.get("wecom", {})
    if wc.get("enabled", False) and wc.get("webhook"):
        notifiers.append(WeComNotifier(wc["webhook"]))
    return notifiers
