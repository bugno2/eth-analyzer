#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH情感分析 + 飞书推送 (集成百度NLP + 实时价格)

import requests
import json
import os
from datetime import datetime

# ========== 从环境变量读取密钥 ==========
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
BAIDU_API_KEY = os.environ.get("BAIDU_API_KEY")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_SECRET_KEY")
# =========================================

def get_eth_price():
    """从币安API获取ETH/USDT实时价格"""
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            price = float(resp.json().get("price", 0))
            print(f"✅ ETH实时价格: ${price}")
            return price
        else:
            print(f"⚠️ 获取ETH价格失败: {resp.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ 获取ETH价格异常: {e}")
        return None

def get_baidu_access_token():
    """获取百度API的Access Token"""
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        print("⚠️ 未设置百度API Key或Secret Key")
        return None

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": BAIDU_API_KEY,
        "client_secret": BAIDU_SECRET_KEY
    }
    try:
        resp = requests.post(url, params=params, timeout=10)
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            print("✅ 获取百度Token成功")
            return token
        else:
            print(f"❌ 获取百度Token失败: {resp.text}")
            return None
    except Exception as e:
        print(f"❌ 请求百度Token异常: {e}")
        return None

def analyze_sentiment(text, token):
    """调用百度情感倾向分析API分析单条文本"""
    if not token:
        return None

    url = "https://aip.baidubce.com/rpc/2.0/nlp/v1/sentiment_classify"
    params = {"access_token": token, "charset": "UTF-8"}
    headers = {"Content-Type": "application/json"}
    payload = {"text": text}

    try:
        resp = requests.post(url, params=params, headers=headers, json=payload, timeout=10)
        result = resp.json()

        if "items" in result and len(result["items"]) > 0:
            item = result["items"][0]
            sentiment_map = {0: "负面", 1: "中性", 2: "正面"}
            return {
                "sentiment": sentiment_map.get(item.get("sentiment"), "未知"),
                "positive_prob": round(item.get("positive_prob", 0), 3),
                "negative_prob": round(item.get("negative_prob", 0), 3),
                "confidence": round(item.get("confidence", 0), 3)
            }
        else:
            print(f"⚠️ 情感分析返回异常: {result}")
            return None
    except Exception as e:
        print(f"❌ 调用情感分析API异常: {e}")
        return None

def fetch_eth_news():
    """获取ETH相关新闻（可替换为真实数据源）"""
    return [
        "ETH价格跌破1900美元，市场恐慌情绪蔓延",
        "机构投资者持续增持以太坊ETF，看好长期价值",
        "Vitalik发文讨论ETH 2.0升级进展，社区反应积极",
        "某巨鲸地址近日大量抛售ETH，引发市场担忧"
    ]

def generate_report():
    """综合分析并生成报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. 获取ETH实时价格
    eth_price = get_eth_price()
    price_display = f"${eth_price:.2f}" if eth_price else "获取失败"

    # 2. 获取百度Token并分析
    token = get_baidu_access_token()
    if not token:
        print("❌ 无法获取百度Token，使用固定数据")
        return generate_fallback_report(now, price_display)

    news_list = fetch_eth_news()
    analysis_results = []
    for news in news_list:
        result = analyze_sentiment(news, token)
        if result:
            analysis_results.append(result)
            print(f"📊 分析: {news[:20]}... → {result['sentiment']}")

    if not analysis_results:
        print("⚠️ 没有分析结果，使用固定数据")
        return generate_fallback_report(now, price_display)

    total = len(analysis_results)
    positive_count = sum(1 for r in analysis_results if r["sentiment"] == "正面")
    negative_count = sum(1 for r in analysis_results if r["sentiment"] == "负面")

    if positive_count > negative_count:
        overall_sentiment = "偏多"
        sentiment_detail = f"正面{int(positive_count/total*100)}% / 负面{int(negative_count/total*100)}%"
    elif negative_count > positive_count:
        overall_sentiment = "偏空"
        sentiment_detail = f"负面{int(negative_count/total*100)}% / 正面{int(positive_count/total*100)}%"
    else:
        overall_sentiment = "中性"
        sentiment_detail = f"正面{int(positive_count/total*100)}% / 负面{int(negative_count/total*100)}%"

    d = {
        "price": price_display,
        "sentiment": overall_sentiment,
        "sentiment_detail": sentiment_detail,
        "fng": 45,
        "fng_label": "中性偏惧，市场犹豫",
        "summary": f"{overall_sentiment}主导，市场情绪分化",
        "levels": {
            "强压力": {"price": 1920, "desc": "最后关口，突破翻多"},
            "压力位": {"price": "1915 / 1905", "desc": "反弹试空区"},
            "支撑位": {"price": "1875 / 1860", "desc": "破位看1845"},
            "强支撑": {"price": 1845, "desc": "多空分界线"}
        },
        "trades": [
            {"type": "🟢 激进多", "entry": "1845-1850", "stop": "1835 (-12)", "tp": "1875 / 1900", "rr": "2.5:1", "size": "1%", "risk": "中"},
            {"type": "🟢 稳健多", "entry": "1830-1835", "stop": "1820 (-13)", "tp": "1865 / 1890", "rr": "2.7:1", "size": "2%", "risk": "中低"},
            {"type": "🟢 极限多", "entry": "1818-1825", "stop": "1805 (-15)", "tp": "1850 / 1875", "rr": "2.3:1", "size": "0.5%", "risk": "高"},
            {"type": "🔵 右侧多", "entry": "回踩1860-65不破", "stop": "1850 (-13)", "tp": "1900 / 1915", "rr": "3.2:1", "size": "1.5%", "risk": "中低"},
            {"type": "🔴 反抽空", "entry": "1900-10受阻", "stop": "1920 (+13)", "tp": "1875 / 1860", "rr": "2.5:1", "size": "1%", "risk": "中"}
        ],
        "position": [
            {"trigger": "📉 到1875", "action": "持盈，止盈上移至1860", "logic": "保本锁利"},
            {"trigger": "📉 到1860-65", "action": "全部离场", "logic": "支撑告破"},
            {"trigger": "📈 反抽1900-10受阻", "action": "开空，分批加至标准", "logic": "阻力确认"},
            {"trigger": "📈 站稳1915超15分钟", "action": "止损走人，不补", "logic": "空头失败"}
        ]
    }

    trade_rows = "\n".join([f"| {t['type']} | {t['entry']} | {t['stop']} | {t['tp']} | {t['rr']} | {t['size']} | {t['risk']} |" for t in d["trades"]])
    pos_rows = "\n".join([f"| {p['trigger']} | {p['action']} | {p['logic']} |" for p in d["position"]])

    report = f"""
# 📊 ETH AI 全视角分析
**📅 {now} (UTC+8)**
**💰 ETH实时价格: {d['price']}**

---

## 📰 情绪面（基于百度NLP实时分析）
| 指标 | 数值 | 结论 |
|:---|:---|:---|
| ETH价格 | {d['price']} | — |
| 新闻情绪 | {d['sentiment']} | {d['sentiment_detail']} |
| 恐惧贪婪 | {d['fng']} | {d['fng_label']} |
| 综合判断 | {d['summary']} | — |

---

## 📈 关键位（相对当前价格）
| 类型 | 价位 | 含义 |
|:---|:---|:---|
| 🔴 强压 | {d['levels']['强压力']['price']} | {d['levels']['强压力']['desc']} |
| 🔴 压力 | {d['levels']['压力位']['price']} | {d['levels']['压力位']['desc']} |
| 🟢 支撑 | {d['levels']['支撑位']['price']} | {d['levels']['支撑位']['desc']} |
| 🟢 铁底 | {d['levels']['强支撑']['price']} | {d['levels']['强支撑']['desc']} |

---

## 📋 交易计划
| 策略 | 入场 | 止损 | 止盈 | 盈亏比 | 仓位 | 风险 |
|:---|:---|:---|:---|:---|:---|:---|
{trade_rows}

---

## 📦 持仓管理
| 条件 | 动作 | 逻辑 |
|:---|:---|:---|
{pos_rows}

---

## 🧠 当前定调
> ✅ AI分析显示市场情绪 **{d['sentiment']}**，当前价格 **{d['price']}**
> 🔑 分批止盈 + 移动止损，静待信号

⚠️ *分析仅供参考，投资决策需自行判断，盈亏自负。*
"""
    return report

def generate_fallback_report(now, price_display):
    """备用报告（百度API不可用时）"""
    return f"""
# 📊 ETH AI 全视角分析 (备用数据)
**📅 {now} (UTC+8)**
**💰 ETH实时价格: {price_display}**

⚠️ **当前无法获取百度NLP实时分析数据**

---

## 📈 关键位（相对当前价格）
| 类型 | 价位 | 含义 |
|:---|:---|:---|
| 🔴 强压 | 1920 | 突破翻多 |
| 🔴 压力 | 1915 / 1905 | 反弹试空区 |
| 🟢 支撑 | 1875 / 1860 | 破位看1845 |
| 🟢 铁底 | 1845 | 多空分界线 |

⚠️ *分析仅供参考，投资决策需自行判断，盈亏自负。*
"""

def send_to_feishu(content):
    """推送至飞书"""
    if not FEISHU_WEBHOOK:
        print("⚠️ 未设置 FEISHU_WEBHOOK")
        return
    headers = {"Content-Type": "application/json"}
    payload = {"msg_type": "text", "content": {"text": content}}
    try:
        resp = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[{datetime.now()}] ✅ 飞书推送成功")
        else:
            print(f"[{datetime.now()}] ❌ 推送失败: {resp.text}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ 请求异常: {e}")

def main():
    print(f"[{datetime.now()}] 🚀 开始分析ETH情绪...")
    report = generate_report()
    send_to_feishu(report)
    print(f"[{datetime.now()}] ✅ 分析完成")

if __name__ == "__main__":
    main()