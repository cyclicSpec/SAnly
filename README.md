# Stock Monitor

万元级别个人股票监控工具，新浪 API 实时行情 + 技术指标分析 + 多通道推送。

## 功能

- 分钟级盘中轮询（新浪 API）
- 技术指标：MA5/10/20/60、MACD、RSI(14)、KDJ
- 收盘结算推送（SQLite 持久化）
- 异动提醒：涨跌幅阈值、放量检测
- 推送渠道：控制台、钉钉、企业微信

## 使用

```bash
pip install pandas
# 编辑 config.json 配置关注股票和推送渠道
python main.py
```

## 依赖

仅 pandas（requests / numpy 作为 transitive 依赖）。
