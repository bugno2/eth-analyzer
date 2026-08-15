#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH智能分析简报 (精准版 v4.2)

import requests
import json
import os
import time
from datetime import datetime, timezone, timedelta

# ========== 环境变量 ==========
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
BAIDU_API_KEY = os.environ.get("BAIDU_API_KEY")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_SECRET_KEY")
# =============================

BEIJING_TZ = timezone(timedelta(hours=8))
VERSION = "v4.2"


def get_beijing_time():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


# ========== 1. 价格获取 ==========

def get_eth_price():
    """获取ETH实时价格"""
    # 方案1: 币安价格API
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            price = float(resp.json().get("price", 0))
            if price > 0:
                return price
    except:
        pass
    
    # 方案2: 币安K线（最新收盘价）
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1m&limit=2"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) >= 1:
                price = float(data[-1][4])
                if price > 0:
                    return price
    except:
        pass
    
    # 方案3: MEXC
    try:
        url = "https://api.mexc.com/api/v3/ticker/price?symbol=ETHUSDT"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            price = float(resp.json().get("price", 0))
            if price > 0:
                return price
    except:
        pass
    
    return None


# ========== 2. 核心计算（缩小波动范围） ==========

def generate_levels(price):
    """基于当前价格生成关键位 - 波动范围缩小"""
    # 根据价格区间设定不同的波动点数（不是百分比）
    # 目标是让支撑/压力在价格附近10-20点范围内
    if price > 2000:
        range_val = 18
    elif price > 1500:
        range_val = 15
    elif price > 1000:
        range_val = 12
    else:
        range_val = 10
    
    # 价格在1800-2000之间时，用15点
    if 1800 <= price <= 2000:
        range_val = 15
    
    return {
        "压力": round(price + range_val, 0),
        "强压": round(price + int(range_val * 1.8), 0),
        "支撑": round(price - range_val, 0),
        "铁底": round(price - int(range_val * 1.8), 0),
        "range_val": range_val
    }


def generate_trade_plan(price, levels):
    """生成交易计划 - 入场价贴近当前价"""
    range_val = levels["range_val"]
    
    # 做多：入场价在当前价下方5-8点
    long_entry = round(price - int(range_val * 0.4), 0)
    # 确保入场价不低于支撑位
    if long_entry < levels["支撑"]:
        long_entry = levels["支撑"] + 1
    
    # 做多止损：入场价下方8-10点
    long_stop = round(long_entry - int(range_val * 0.6), 0)
    if long_stop < levels["铁底"]:
        long_stop = levels["铁底"] + 1
    
    # 做多止盈：入场价上方10-15点
    long_tp1 = round(long_entry + int(range_val * 0.7), 0)
    long_tp2 = round(long_entry + int(range_val * 1.3), 0)
    if long_tp1 > levels["压力"]:
        long_tp1 = levels["压力"] - 1
    if long_tp2 > levels["强压"]:
        long_tp2 = levels["强压"] - 1
    
    # 做空：入场价在当前价上方5-8点
    short_entry = round(price + int(range_val * 0.4), 0)
    if short_entry > levels["压力"]:
        short_entry = levels["压力"] - 1
    
    # 做空止损：入场价上方8-10点
    short_stop = round(short_entry + int(range_val * 0.6), 0)
    if short_stop > levels["强压"]:
        short_stop = levels["强压"] - 1
    
    # 做空止盈：入场价下方10-15点
    short_tp1 = round(short_entry - int(range_val * 0.7), 0)
    short_tp2 = round(short_entry - int(range_val * 1.3), 0)
    if short_tp1 < levels["支撑"]:
        short_tp1 = levels["支撑"] + 1
    if short_tp2 < levels["铁底"]:
        short_tp2 = levels["铁底"] + 1
    
    return {
        "long_entry": long_entry,
        "long_stop": long_stop,
        "long_tp1": long_tp1,
        "long_tp2": long_tp2,
        "short_entry": short_entry,
        "short_stop": short_stop,
        "short_tp1": short_tp1,
        "short_tp2": short_tp2
    }


# ========== 3. 恐惧贪婪 ==========

def get_fng():
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()["data"][0]
            return {"value": int(data["value"]), "label": data["value_classification"]}
    except:
        pass
    return {"value": 50, "label": "中性"}


# ========== 4. 推送 ==========

def send_to_feishu(content):
    if not FEISHU_WEBHOOK:
        return False
    for i in range(3):
        try:
            resp = requests.post(
                FEISHU_WEBHOOK,
                headers={"Content-Type": "application/json"},
                json={"msg_type": "text", "content": {"text": content}},
                timeout=10
            )
            if resp.status_code == 200:
                return True
        except:
            pass
        time.sleep(2)
    return False


# ========== 5. 报告生成 ==========

def generate_report():
    now = get_beijing_time()
    
    price = get_eth_price()
    if not price or price <= 0:
        error_report = f"""
📊 ETH 智能分析简报
⏰ {now}
💰 价格: ❌ 数据获取失败

⚠️ 无法获取ETH实时价格，请检查网络连接或稍后再试。

📌 {VERSION} | 仅供参考
"""
        return error_report
    
    price = round(price, 0)
    
    # 生成数据
    levels = generate_levels(price)
    plan = generate_trade_plan(price, levels)
    fng = get_fng()
    
    # 评分
    s_score = "强支撑" if price - levels["支撑"] < 3 else "中等支撑" if price - levels["支撑"] < 8 else "弱支撑"
    r_score = "强压力" if levels["压力"] - price < 3 else "中等压力" if levels["压力"] - price < 8 else "弱压力"
    
    # 风险
    risk_score = 0
    if price >= levels["强压"]:
        risk_score += 25
    elif price >= levels["压力"]:
        risk_score += 15
    if price <= levels["支撑"]:
        risk_score += 15
    elif price <= levels["铁底"]:
        risk_score += 25
    if fng["value"] >= 70:
        risk_score += 15
    elif fng["value"] <= 25:
        risk_score += 15
    risk = "高风险 🔴" if risk_score >= 60 else "中等风险 🟡" if risk_score >= 40 else "低风险 🟢"
    
    # 建议
    s, r = levels["支撑"], levels["压力"]
    if price < s + 3:
        advice = f"🟢 接近支撑 {s}，关注反弹"
    elif price > r - 3:
        advice = f"🔴 接近压力 {r}，注意回调"
    else:
        advice = f"🟡 区间震荡，{s} 做多，{r} 做空"
    
    # 摘要
    if price < levels["支撑"]:
        summary = "📌 跌破支撑，观望为主"
    elif price > levels["压力"]:
        summary = "📌 突破压力，关注追多"
    else:
        summary = "📌 震荡行情，高抛低吸"
    
    # 关注点
    focus = []
    if price - levels["支撑"] < 5:
        focus.append(f"📍 关注 {levels['支撑']} 支撑有效性")
    if levels["压力"] - price < 5:
        focus.append(f"📍 关注 {levels['压力']} 压力能否突破")
    if fng["value"] <= 25:
        focus.append("📍 市场恐慌，关注超跌反弹")
    elif fng["value"] >= 70:
        focus.append("📍 市场贪婪，注意回调风险")
    if not focus:
        focus.append("📍 区间震荡，等待方向")
    
    range_display = f"日内区间: ${levels['支撑']} - ${levels['压力']}（{levels['range_val']}点）"
    
    report = f"""
📊 ETH 智能分析简报
⏰ {now}
💰 价格: ${price}
📊 {range_display}

📌 {summary}
🎯 {advice}

📰 情绪: 中性 | 恐惧贪婪: {fng['value']}（{fng['label']}）

📈 关键位
🔴 压力: {levels['压力']}（{r_score}）
🟢 支撑: {levels['支撑']}（{s_score}）
🔴 强压: {levels['强压']} | 🟢 铁底: {levels['铁底']}

📋 操作参考
【做多】入场 {plan['long_entry']} | 止损 {plan['long_stop']} | 止盈 {plan['long_tp1']}/{plan['long_tp2']}
【做空】入场 {plan['short_entry']} | 止损 {plan['short_stop']} | 止盈 {plan['short_tp1']}/{plan['short_tp2']}

📊 市场数据
⚡ 波动幅度: {levels['range_val']}点
⚠️ 风险等级: {risk}

🔍 今日关注
{chr(10).join(focus[:3])}

📌 {VERSION} | 仅供参考，风险自担
"""
    return report


def main():
    print(f"[{get_beijing_time()}] 🚀 开始分析...")
    report = generate_report()
    if send_to_feishu(report):
        print(f"[{get_beijing_time()}] ✅ 推送成功")
    else:
        print(f"[{get_beijing_time()}] ❌ 推送失败")


if __name__ == "__main__":
    main()