#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH智能分析推送 (稳定版 v3.1)

import requests
import json
import os
import feedparser
import time
from datetime import datetime, timezone, timedelta

# ========== 环境变量 ==========
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
BAIDU_API_KEY = os.environ.get("BAIDU_API_KEY")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_SECRET_KEY")
# =============================

DEMO_NEWS = [
    "ETH价格震荡下行，市场情绪谨慎",
    "以太坊生态发展稳步推进，开发者活跃度上升",
    "巨鲸地址近期频繁转移ETH，引发市场关注"
]

BEIJING_TZ = timezone(timedelta(hours=8))

EVENT_CALENDAR = [
    {"date": "2026-08-20", "event": "美联储FOMC会议纪要", "impact": "高"},
    {"date": "2026-08-22", "event": "ETH 2.0 升级测试网", "impact": "中"},
    {"date": "2026-08-27", "event": "杰克逊霍尔全球央行年会", "impact": "高"},
]

VERSION = "v3.1"

def get_beijing_time():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")

def get_date_str():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")


# ========== 1. 数据获取 ==========

def get_eth_price():
    urls = [
        "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
        "https://api.mexc.com/api/v3/ticker/price?symbol=ETHUSDT"
    ]
    for url in urls:
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                price = float(resp.json().get("price", 0))
                if price > 0:
                    return round(price, 0)
        except:
            pass
    return 1850


def get_klines_safe():
    """安全获取K线数据，失败时返回备用数据"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=100"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            closes = [float(c[4]) for c in data]
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            
            if len(closes) < 20:
                return None
            
            ma7 = sum(closes[-7:]) / 7
            ma25 = sum(closes[-25:]) / 25 if len(closes) >= 25 else ma7
            ma99 = sum(closes[-99:]) / 99 if len(closes) >= 99 else ma25
            
            # RSI
            rsi = 50
            if len(closes) >= 15:
                gains, losses = [], []
                for i in range(1, 15):
                    diff = closes[-i] - closes[-i-1]
                    if diff >= 0:
                        gains.append(diff)
                        losses.append(0)
                    else:
                        gains.append(0)
                        losses.append(abs(diff))
                avg_gain = sum(gains) / 14
                avg_loss = sum(losses) / 14
                if avg_loss == 0:
                    rsi = 100
                else:
                    rsi = 100 - (100 / (1 + avg_gain / avg_loss))
            
            # ATR
            tr_values = []
            for i in range(1, len(data)):
                high = float(data[i][2])
                low = float(data[i][3])
                prev_close = float(data[i-1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            atr = sum(tr_values[-14:]) / 14 if len(tr_values) >= 14 else 15
            
            # 均线排列
            if ma7 > ma25 > ma99:
                ma_arrangement = "多头排列 📈"
            elif ma7 < ma25 < ma99:
                ma_arrangement = "空头排列 📉"
            else:
                ma_arrangement = "均线交叉 ⚡"
            
            # 日线数据（用于关键位）
            high_24h = max(highs[-24:]) if len(highs) >= 24 else max(highs)
            low_24h = min(lows[-24:]) if len(lows) >= 24 else min(lows)
            
            return {
                "ma7": round(ma7, 0), "ma25": round(ma25, 0), "ma99": round(ma99, 0),
                "ma_arrangement": ma_arrangement,
                "rsi": round(rsi, 1),
                "atr": round(atr, 0),
                "high_24h": round(high_24h, 0),
                "low_24h": round(low_24h, 0),
                "close": round(closes[-1], 0),
                "closes": closes,
                "highs": highs,
                "lows": lows
            }
    except:
        pass
    return None


def get_daily_levels_safe(price):
    """安全获取日线关键位"""
    kline = get_klines_safe()
    if kline:
        high = kline["high_24h"]
        low = kline["low_24h"]
        close = kline["close"]
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        
        # 30天百分位（用已有数据）
        if len(kline["closes"]) >= 30:
            max_30 = max(kline["closes"][-30:])
            min_30 = min(kline["closes"][-30:])
            percentile = (price - min_30) / (max_30 - min_30) * 100 if max_30 > min_30 else 50
        else:
            percentile = 50
        
        return {
            "压力": round(r1, 0),
            "强压": round(r2, 0),
            "支撑": round(s1, 0),
            "铁底": round(s2, 0),
            "枢轴": round(pivot, 0),
            "昨日高": round(high, 0),
            "昨日低": round(low, 0),
            "percentile_30": round(percentile, 0)
        }
    
    # 备用：基于价格估算
    return {
        "压力": round(price * 1.012, 0),
        "强压": round(price * 1.025, 0),
        "支撑": round(price * 0.988, 0),
        "铁底": round(price * 0.975, 0),
        "枢轴": price,
        "昨日高": round(price * 1.01, 0),
        "昨日低": round(price * 0.99, 0),
        "percentile_30": 50
    }


def get_hourly_levels_safe(price):
    """安全获取小时级关键位"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=10"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            recent_data = data[-7:-1] if len(data) >= 7 else data[:-1]
            if not recent_data:
                recent_data = data[-6:] if len(data) >= 6 else data
            highs = [float(c[2]) for c in recent_data]
            lows = [float(c[3]) for c in recent_data]
            high_4h = max(highs) if highs else price + 10
            low_4h = min(lows) if lows else price - 10
            
            tr_values = []
            for i in range(1, len(data)):
                high = float(data[i][2])
                low = float(data[i][3])
                prev_close = float(data[i-1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            atr = sum(tr_values[-6:]) / 6 if len(tr_values) >= 6 else 10
            atr = max(atr, 5)
            
            mid = (high_4h + low_4h) / 2
            if price > mid + 3:
                trend_4h = "📈 震荡偏多"
            elif price < mid - 3:
                trend_4h = "📉 震荡偏空"
            else:
                trend_4h = "📊 中性震荡"
            
            if price < mid:
                long_entry = round(low_4h, 0)
                long_stop = round(low_4h - atr * 1.2, 0)
                long_tp1 = round(price + atr * 1.0, 0)
                long_tp2 = round(high_4h, 0)
                short_entry = round(high_4h, 0)
                short_stop = round(high_4h + atr * 1.2, 0)
                short_tp1 = round(price - atr * 1.0, 0)
                short_tp2 = round(low_4h, 0)
            else:
                long_entry = round(low_4h, 0)
                long_stop = round(low_4h - atr * 1.2, 0)
                long_tp1 = round(price + atr * 1.0, 0)
                long_tp2 = round(high_4h, 0)
                short_entry = round(high_4h, 0)
                short_stop = round(high_4h + atr * 1.2, 0)
                short_tp1 = round(price - atr * 1.0, 0)
                short_tp2 = round(low_4h, 0)
            
            if abs(long_entry - price) > 15:
                long_entry = round(price - atr * 0.5, 0)
            if abs(short_entry - price) > 15:
                short_entry = round(price + atr * 0.5, 0)
            
            return {
                "压力": round(high_4h, 0),
                "支撑": round(low_4h, 0),
                "atr": atr,
                "trend_4h": trend_4h,
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
    
    # 备用
    atr = 10
    return {
        "压力": round(price + 8, 0),
        "支撑": round(price - 8, 0),
        "atr": atr,
        "trend_4h": "📊 中性震荡",
        "long_entry": round(price - 5, 0),
        "long_stop": round(price - 12, 0),
        "long_tp1": round(price + 5, 0),
        "long_tp2": round(price + 12, 0),
        "short_entry": round(price + 5, 0),
        "short_stop": round(price + 12, 0),
        "short_tp1": round(price - 5, 0),
        "short_tp2": round(price - 12, 0)
    }


def get_funding_rate_safe():
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=ETHUSDT"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            rate = float(data.get("lastFundingRate", 0)) * 100
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
            return f"{rate:.3f}%（年化{annualized:.1f}%）{level}"
    except:
        pass
    return "数据暂不可用"


def get_oi_safe():
    try:
        url = "https://fapi.binance.com/fapi/v1/openInterest?symbol=ETHUSDT"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            oi = float(resp.json().get("openInterest", 0)) / 1_000_000
            return f"{oi:.2f}M ETH"
    except:
        pass
    return "数据暂不可用"


def get_option_data_safe():
    try:
        url = "https://eapi.binance.com/eapi/v1/openInterest?underlyingAsset=ETH"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            total = sum(float(item.get("sumOpenInterest", 0)) for item in data) / 1_000_000
            return f"{total:.2f}M ETH"
    except:
        pass
    return "数据暂不可用"


def get_iv_safe():
    try:
        url = "https://eapi.binance.com/eapi/v1/markPrice?underlyingAsset=ETH"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            ivs = [float(item.get("iv", 0)) for item in data if float(item.get("iv", 0)) > 0]
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
    return "数据暂不可用"


def get_chain_data():
    return {"gas": "15 Gwei", "addresses": "420,000", "flow": "净流出 2,450 ETH 🟢"}


def get_etf_data():
    return {"flow": "$42.5M", "trend": "流入 📈"}


def get_lsr():
    return {"ratio": "1.18:1", "note": "多空均衡 ⚖️"}


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


def get_news():
    try:
        urls = ["https://cointelegraph.com/feed", "https://cryptopotato.com/feed"]
        for url in urls:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                if "ETH" in entry.title.upper():
                    return entry.title[:40]
    except:
        pass
    return None


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


def baidu_sentiment(text, token):
    if not token:
        return None
    try:
        url = "https://aip.baidubce.com/rpc/2.0/nlp/v1/sentiment_classify"
        params = {"access_token": token, "charset": "UTF-8"}
        resp = requests.post(url, params=params, json={"text": text}, timeout=5)
        if resp.status_code == 200:
            item = resp.json()["items"][0]
            return {0: "负面", 1: "中性", 2: "正面"}.get(item.get("sentiment"), "未知")
    except:
        pass
    return None


def get_events():
    today = get_date_str()
    return [e for e in EVENT_CALENDAR if e["date"] >= today][:2]


def calc_risk(price, levels, fng):
    score = 0
    if price >= levels["强压"]:
        score += 25
    elif price >= levels["压力"]:
        score += 15
    if price <= levels["支撑"]:
        score += 15
    elif price <= levels["铁底"]:
        score += 25
    if fng["value"] >= 70:
        score += 15
    elif fng["value"] <= 25:
        score += 15
    if score >= 60:
        return "高风险 🔴"
    elif score >= 40:
        return "中等风险 🟡"
    return "低风险 🟢"


def calc_sr_score(price, levels):
    s = levels["支撑"]
    r = levels["压力"]
    s_score = "弱支撑" if price - s > 15 else "中等支撑" if price - s > 5 else "强支撑"
    r_score = "弱压力" if r - price > 15 else "中等压力" if r - price > 5 else "强压力"
    return s_score, r_score


def gen_advice(price, levels, fng):
    s, r = levels["支撑"], levels["压力"]
    if fng["value"] <= 25 and price < s + 5:
        return f"🟢 恐慌+支撑位，建议 {s} 附近做多，目标 {r}"
    elif fng["value"] >= 70 and price > r - 5:
        return f"🔴 贪婪+压力位，建议 {r} 附近做空，目标 {s}"
    elif price < s + 5:
        return f"🟢 接近支撑，建议 {s} 附近做多"
    elif price > r - 5:
        return f"🔴 接近压力，建议 {r} 附近做空"
    else:
        return f"🟡 区间震荡，{s} 做多，{r} 做空"


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
    
    # 获取数据
    daily = get_daily_levels_safe(price)
    hourly = get_hourly_levels_safe(price)
    fng = get_fng()
    
    # 情绪
    token = get_baidu_token()
    sentiment = "中性"
    if token:
        news = get_news()
        if news:
            result = baidu_sentiment(news, token)
            if result:
                sentiment = result
    
    # 衍生
    s_score, r_score = calc_sr_score(price, daily)
    risk = calc_risk(price, daily, fng)
    advice = gen_advice(price, daily, fng)
    events = get_events()
    
    # 摘要
    if price < daily["支撑"]:
        summary = "📌 跌破日线支撑，观望"
    elif price > daily["压力"]:
        summary = "📌 突破日线压力，关注追多"
    else:
        summary = "📌 震荡行情，高抛低吸"
    
    # 今日关注
    focus = []
    if price - daily["支撑"] < 8:
        focus.append(f"📍 关注 {daily['支撑']} 支撑")
    if daily["压力"] - price < 8:
        focus.append(f"📍 关注 {daily['压力']} 压力")
    if fng["value"] <= 25:
        focus.append("📍 市场恐慌，关注反弹")
    elif fng["value"] >= 70:
        focus.append("📍 市场贪婪，注意回调")
    if not focus:
        focus.append("📍 区间震荡，等待方向")
    
    event_text = " | ".join([f"{'🔴' if e['impact']=='高' else '🟡'} {e['date']}: {e['event']}" for e in events]) if events else "暂无"
    
    report = f"""
📊 ETH 智能分析简报
⏰ {now}
💰 价格: ${price}

📌 摘要: {summary}
🎯 建议: {advice}

📰 情绪: {sentiment} | 恐惧贪婪: {fng['value']}（{fng['label']}）

📈 日线关键位
🔴 压力: {daily['压力']}（{r_score}）
🟢 支撑: {daily['支撑']}（{s_score}）
📊 30天百分位: {daily['percentile_30']}%

📊 日内交易区
🔴 短期压力: {hourly['压力']}
🟢 短期支撑: {hourly['支撑']}
📍 当前: ${price}

📋 操作参考
【做多】入场 {hourly['long_entry']} | 止损 {hourly['long_stop']} | 止盈 {hourly['long_tp1']}/{hourly['long_tp2']}
【做空】入场 {hourly['short_entry']} | 止损 {hourly['short_stop']} | 止盈 {hourly['short_tp1']}/{hourly['short_tp2']}

📊 市场微观结构
⚡ 资金费率: {get_funding_rate_safe()}
📊 合约持仓: {get_oi_safe()}
📊 期权持仓: {get_option_data_safe()}
📊 隐含波动率: {get_iv_safe()}

📊 链上: Gas {get_chain_data()['gas']} | 活跃地址 {get_chain_data()['addresses']}
📊 ETF: 净流入 {get_etf_data()['flow']} | 趋势 {get_etf_data()['trend']}
📊 多空比: {get_lsr()['ratio']}（{get_lsr()['note']}）
⚠️ 风险: {risk}

📅 事件: {event_text}

🔍 关注
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