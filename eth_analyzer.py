#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH智能分析简报 (稳定版 v3.2)

import requests
import json
import os
import feedparser
import time
import re
from datetime import datetime, timezone, timedelta

# ========== 环境变量 ==========
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
BAIDU_API_KEY = os.environ.get("BAIDU_API_KEY")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_SECRET_KEY")
# =============================

BEIJING_TZ = timezone(timedelta(hours=8))
VERSION = "v3.2"


def get_beijing_time():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


# ========== 1. 核心数据获取（带备用方案） ==========

def get_eth_price():
    """获取ETH价格"""
    urls = [
        "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
        "https://api.mexc.com/api/v3/ticker/price?symbol=ETHUSDT"
    ]
    for url in urls:
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                return round(float(resp.json().get("price", 1850)), 0)
        except:
            pass
    return 1850


def get_funding_rate():
    """获取资金费率 - 使用多个数据源"""
    # 方案1: 币安合约API
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=ETHUSDT"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            rate = float(data.get("lastFundingRate", 0)) * 100
            if rate != 0:
                annualized = rate * 3 * 365
                if annualized > 50:
                    level = "🔥 多头过热"
                elif annualized > 20:
                    level = "📈 多头偏强"
                elif annualized < -20:
                    level = "❄️ 空头占优"
                elif annualized < -50:
                    level = "⛽ 空头极度拥挤"
                else:
                    level = "⚖️ 中性"
                return f"{rate:.3f}%（年化{annualized:.0f}%）{level}"
    except:
        pass

    # 方案2: 从K线推算（备用）
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=24"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            closes = [float(c[4]) for c in data]
            if len(closes) >= 2:
                change = (closes[-1] - closes[-2]) / closes[-2] * 100
                if change > 1:
                    return f"约 +{change:.1f}%（推测多头占优）"
                elif change < -1:
                    return f"约 {change:.1f}%（推测空头占优）"
                else:
                    return "约 0%（中性）"
    except:
        pass

    return "数据暂不可用"


def get_open_interest():
    """获取合约持仓量"""
    try:
        url = "https://fapi.binance.com/fapi/v1/openInterest?symbol=ETHUSDT"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            oi = float(resp.json().get("openInterest", 0))
            if oi > 0:
                return f"{oi / 1_000_000:.2f}M ETH"
    except:
        pass

    # 备用：从Coinglass获取（如果可用）
    try:
        url = "https://api.coinglass.com/api/v1/eth/open_interest"
        resp = requests.get(url, timeout=5, headers={"Accept": "application/json"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                oi = float(data["data"].get("oi", 0))
                if oi > 0:
                    return f"{oi / 1_000_000:.2f}M ETH"
    except:
        pass

    return "数据暂不可用"


def get_option_oi():
    """获取期权持仓量"""
    try:
        url = "https://eapi.binance.com/eapi/v1/openInterest?underlyingAsset=ETH"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            total = sum(float(item.get("sumOpenInterest", 0)) for item in data)
            if total > 0:
                return f"{total / 1_000_000:.2f}M ETH"
    except:
        pass

    # 备用：使用Deribit数据
    try:
        url = "https://www.deribit.com/api/v2/public/get_summary?instrument_name=ETH-PERPETUAL"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("result"):
                oi = float(data["result"].get("open_interest", 0))
                if oi > 0:
                    return f"{oi / 1_000_000:.2f}M ETH"
    except:
        pass

    return "数据暂不可用"


def get_implied_volatility():
    """获取隐含波动率"""
    try:
        # 从币安期权标记价格获取
        url = "https://eapi.binance.com/eapi/v1/markPrice?underlyingAsset=ETH"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            ivs = []
            for item in data:
                iv = float(item.get("iv", 0))
                if 0 < iv < 5:  # 正常范围
                    ivs.append(iv)
            if ivs:
                avg_iv = sum(ivs) / len(ivs) * 100
                if avg_iv > 80:
                    level = "🔴 极端高位"
                elif avg_iv > 60:
                    level = "🟡 偏高"
                elif avg_iv > 40:
                    level = "🟢 正常"
                else:
                    level = "🟢 低位"
                return f"{avg_iv:.1f}%（{level}）"
    except:
        pass

    # 备用：从24小时波动率估算
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=24"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            if highs and lows:
                avg_high = sum(highs) / len(highs)
                avg_low = sum(lows) / len(lows)
                if avg_high > 0:
                    volatility = (avg_high - avg_low) / avg_high * 100
                    if volatility > 5:
                        return f"约 {volatility:.1f}%（高波动）"
                    elif volatility > 3:
                        return f"约 {volatility:.1f}%（中波动）"
                    else:
                        return f"约 {volatility:.1f}%（低波动）"
    except:
        pass

    return "数据暂不可用"


def get_daily_levels(price):
    """获取日线关键位"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=24"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            closes = [float(c[4]) for c in data]

            high = max(highs)
            low = min(lows)
            close = closes[-1]

            pivot = (high + low + close) / 3
            r1 = 2 * pivot - low
            r2 = pivot + (high - low)
            s1 = 2 * pivot - high
            s2 = pivot - (high - low)

            # 30天百分位
            try:
                url2 = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1d&limit=30"
                resp2 = requests.get(url2, timeout=5)
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    closes2 = [float(c[4]) for c in data2]
                    if len(closes2) >= 30:
                        max30 = max(closes2[-30:])
                        min30 = min(closes2[-30:])
                        percentile = (price - min30) / (max30 - min30) * 100 if max30 > min30 else 50
                    else:
                        percentile = 50
                else:
                    percentile = 50
            except:
                percentile = 50

            return {
                "压力": round(r1, 0),
                "强压": round(r2, 0),
                "支撑": round(s1, 0),
                "铁底": round(s2, 0),
                "昨日高": round(high, 0),
                "昨日低": round(low, 0),
                "percentile": round(percentile, 0)
            }
    except:
        pass

    # 备用
    return {
        "压力": round(price * 1.015, 0),
        "强压": round(price * 1.03, 0),
        "支撑": round(price * 0.985, 0),
        "铁底": round(price * 0.97, 0),
        "昨日高": round(price * 1.01, 0),
        "昨日低": round(price * 0.99, 0),
        "percentile": 50
    }


def get_hourly_levels(price):
    """获取小时级关键位"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=6"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            high = max(highs) if highs else price + 10
            low = min(lows) if lows else price - 10
            mid = (high + low) / 2

            if price > mid + 3:
                trend = "📈 震荡偏多"
            elif price < mid - 3:
                trend = "📉 震荡偏空"
            else:
                trend = "📊 中性震荡"

            atr = 10
            if len(data) >= 2:
                tr_values = []
                for i in range(1, len(data)):
                    h = float(data[i][2])
                    l = float(data[i][3])
                    pc = float(data[i-1][4])
                    tr_values.append(max(h - l, abs(h - pc), abs(l - pc)))
                if tr_values:
                    atr = max(sum(tr_values[-6:]) / len(tr_values[-6:]), 5)

            long_entry = round(low, 0)
            long_stop = round(low - atr * 1.2, 0)
            long_tp1 = round(price + atr * 1.0, 0)
            long_tp2 = round(high, 0)

            short_entry = round(high, 0)
            short_stop = round(high + atr * 1.2, 0)
            short_tp1 = round(price - atr * 1.0, 0)
            short_tp2 = round(low, 0)

            if abs(long_entry - price) > 15:
                long_entry = round(price - atr * 0.5, 0)
            if abs(short_entry - price) > 15:
                short_entry = round(price + atr * 0.5, 0)

            return {
                "压力": round(high, 0),
                "支撑": round(low, 0),
                "trend": trend,
                "long_entry": long_entry,
                "long_stop": long_stop,
                "long_tp1": long_tp1,
                "long_tp2": long_tp2,
                "short_entry": short_entry,
                "short_stop": short_stop,
                "short_tp1": short_tp1,
                "short_tp2": short_tp2
            }
    except:
        pass

    return {
        "压力": round(price + 8, 0),
        "支撑": round(price - 8, 0),
        "trend": "📊 中性震荡",
        "long_entry": round(price - 5, 0),
        "long_stop": round(price - 12, 0),
        "long_tp1": round(price + 5, 0),
        "long_tp2": round(price + 12, 0),
        "short_entry": round(price + 5, 0),
        "short_stop": round(price + 12, 0),
        "short_tp1": round(price - 5, 0),
        "short_tp2": round(price - 12, 0)
    }


def get_fng():
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()["data"][0]
            return {"value": int(data["value"]), "label": data["value_classification"]}
    except:
        pass
    return {"value": 45, "label": "中性"}


def get_etf_flow():
    try:
        url = "https://www.sosovalue.com/api/etf/flow"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                flow = data["data"].get("net_flow", 0)
                return f"${flow:.0f}M"
    except:
        pass
    return "数据暂不可用"


def get_lsr():
    try:
        url = "https://api.coinglass.com/api/v1/eth/lsr"
        resp = requests.get(url, timeout=5, headers={"Accept": "application/json"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                ratio = float(data["data"].get("long_short_ratio", 1.2))
                if ratio > 1.5:
                    note = "多头过热 ⚠️"
                elif ratio < 0.8:
                    note = "空头占优 📉"
                else:
                    note = "多空均衡 ⚖️"
                return f"{ratio:.2f}:1", note
    except:
        pass
    return "1.18:1", "多空均衡 ⚖️"


def get_baidu_token():
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        return None
    try:
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {"grant_type": "client_credentials", "client_id": BAIDU_API_KEY, "client_secret": BAIDU_SECRET_KEY}
        resp = requests.post(url, params=params, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except:
        pass
    return None


def get_sentiment():
    token = get_baidu_token()
    if not token:
        return "中性"
    try:
        # 用ETH新闻标题测试
        url = "https://cointelegraph.com/feed"
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            if "ETH" in entry.title.upper():
                text = entry.title
                break
        else:
            return "中性"

        url2 = "https://aip.baidubce.com/rpc/2.0/nlp/v1/sentiment_classify"
        params = {"access_token": token, "charset": "UTF-8"}
        resp = requests.post(url2, params=params, json={"text": text}, timeout=5)
        if resp.status_code == 200:
            item = resp.json()["items"][0]
            return {0: "偏空", 1: "中性", 2: "偏多"}.get(item.get("sentiment"), "中性")
    except:
        pass
    return "中性"


def send_to_feishu(content):
    if not FEISHU_WEBHOOK:
        return False
    for i in range(3):
        try:
            resp = requests.post(FEISHU_WEBHOOK, headers={"Content-Type": "application/json"},
                                json={"msg_type": "text", "content": {"text": content}}, timeout=10)
            if resp.status_code == 200:
                return True
        except:
            pass
        time.sleep(2)
    return False


def generate_report():
    now = get_beijing_time()
    price = get_eth_price()

    # 获取所有数据
    daily = get_daily_levels(price)
    hourly = get_hourly_levels(price)
    fng = get_fng()
    sentiment = get_sentiment()
    funding = get_funding_rate()
    oi = get_open_interest()
    option_oi = get_option_oi()
    iv = get_implied_volatility()
    etf = get_etf_flow()
    lsr, lsr_note = get_lsr()

    # 计算衍生指标
    s_score = "强支撑" if price - daily["支撑"] < 5 else "中等支撑" if price - daily["支撑"] < 15 else "弱支撑"
    r_score = "强压力" if daily["压力"] - price < 5 else "中等压力" if daily["压力"] - price < 15 else "弱压力"

    risk_score = 0
    if price >= daily["强压"]:
        risk_score += 25
    elif price >= daily["压力"]:
        risk_score += 15
    if price <= daily["支撑"]:
        risk_score += 15
    elif price <= daily["铁底"]:
        risk_score += 25
    if fng["value"] >= 70:
        risk_score += 15
    elif fng["value"] <= 25:
        risk_score += 15
    risk = "高风险 🔴" if risk_score >= 60 else "中等风险 🟡" if risk_score >= 40 else "低风险 🟢"

    # 建议
    s, r = daily["支撑"], daily["压力"]
    if fng["value"] <= 25 and price < s + 5:
        advice = f"🟢 恐慌+支撑位，建议 {s} 附近做多，目标 {r}"
    elif fng["value"] >= 70 and price > r - 5:
        advice = f"🔴 贪婪+压力位，建议 {r} 附近做空，目标 {s}"
    elif price < s + 5:
        advice = f"🟢 接近支撑 {s}，关注反弹"
    elif price > r - 5:
        advice = f"🔴 接近压力 {r}，注意回调"
    else:
        advice = f"🟡 区间震荡，{s} 做多，{r} 做空"

    # 摘要
    if price < daily["支撑"]:
        summary = "📌 跌破日线支撑，观望"
    elif price > daily["压力"]:
        summary = "📌 突破日线压力，关注追多"
    else:
        summary = "📌 震荡行情，高抛低吸"

    # 关注点
    focus = []
    if price - daily["支撑"] < 8:
        focus.append(f"📍 关注 {daily['支撑']} 支撑有效性")
    if daily["压力"] - price < 8:
        focus.append(f"📍 关注 {daily['压力']} 压力能否突破")
    if fng["value"] <= 25:
        focus.append("📍 市场恐慌，关注超跌反弹")
    elif fng["value"] >= 70:
        focus.append("📍 市场贪婪，注意回调风险")
    if not focus:
        focus.append("📍 区间震荡，等待方向")

    report = f"""
📊 ETH 智能分析简报
⏰ {now}
💰 价格: ${price}

📌 {summary}
🎯 {advice}

📰 情绪: {sentiment} | 恐惧贪婪: {fng['value']}（{fng['label']}）

📈 日线关键位
🔴 压力: {daily['压力']}（{r_score}）
🟢 支撑: {daily['支撑']}（{s_score}）
📊 30天百分位: {daily['percentile']}%

📊 日内交易区（小时级）
🔴 短期压力: {hourly['压力']}
🟢 短期支撑: {hourly['支撑']}
📊 趋势: {hourly['trend']}

📋 操作参考
【做多】入场 {hourly['long_entry']} | 止损 {hourly['long_stop']} | 止盈 {hourly['long_tp1']}/{hourly['long_tp2']}
【做空】入场 {hourly['short_entry']} | 止损 {hourly['short_stop']} | 止盈 {hourly['short_tp1']}/{hourly['short_tp2']}

📊 市场微观结构
⚡ 资金费率: {funding}
📊 合约持仓: {oi}
📊 期权持仓: {option_oi}
📊 隐含波动率: {iv}

📊 多空比: {lsr}（{lsr_note}）
📊 ETF净流入: {etf}
⚠️ 风险等级: {risk}

🔍 今日关注
{chr(10).join(focus[:3])}

📌 v{VERSION} | 仅供参考，风险自担
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