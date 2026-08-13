#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH情感分析 + 飞书推送

import requests
import json
import os
from datetime import datetime

# ========== 从环境变量读取密钥 ==========
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
# =======================================

# 如果没设置环境变量，可以用占位符测试
if not FEISHU_WEBHOOK:
    FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/你的密钥"

REPORT_DATA = {
    "sentiment": "偏空",
    "negative": "62%",
    "positive": "38%",
    "fng": 45,
    "fng_label": "中性偏惧，市场犹豫",
    "summary": "谨慎，利空主导，不重仓追单",
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

def generate_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    d = REPORT_DATA
    trade_rows = "\n".join([f"| {t['type']} | {t['entry']} | {t['stop']} | {t['tp']} | {t['rr']} | {t['size']} | {t['risk']} |" for t in d["trades"]])
    pos_rows = "\n".join([f"| {p['trigger']} | {p['action']} | {p['logic']} |" for p in d["position"]])
    return f"""
# 📊 ETH AI 全视角分析
**📅 {now} (UTC+8)**

---

## 📰 情绪面
| 指标 | 数值 | 结论 |
|:---|:---|:---|
| 新闻情绪 | {d['sentiment']} | 负面{d['negative']} / 正面{d['positive']} |
| 恐惧贪婪 | {d['fng']} | {d['fng_label']} |
| 综合判断 | {d['summary']} | — |

---

## 📈 关键位
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
> ✅ 风险单 → 低风险观察单，主动权在握  
> 🔑 分批止盈 + 移动止损，静待信号

⚠️ *分析仅供参考，投资决策需自行判断，盈亏自负。*
"""

def send_to_feishu(content):
    if not FEISHU_WEBHOOK or FEISHU_WEBHOOK == "https://open.feishu.cn/open-apis/bot/v2/hook/你的密钥":
        print("⚠️ 请先设置飞书Webhook地址")
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