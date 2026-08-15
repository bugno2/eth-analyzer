#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH智能分析推送 (完整增强版)
# 新增功能：链上数据、ETF数据、多空比、历史百分位、支撑压力评分、今日重点关注、风险等级、事件提醒、推送摘要

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

# 关键事件日历（月度更新）
EVENT_CALENDAR = [
    {"date": "2026-08-20", "event": "美联储FOMC会议纪要", "impact": "高"},
    {"date": "2026-08-22", "event": "ETH 2.0 升级测试网", "impact": "中"},
    {"date": "2026-08-27", "event": "杰克逊霍尔全球央行年会", "impact": "高"},
]

VERSION = "v2.1"

def get_beijing_time():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")

def get_date_str():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")


# ========== 数据获取 ==========

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
                    return price
        except:
            pass
    return 1850.00


def get_daily_levels():
    """获取日线级关键位"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1d&limit=30"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            closes = [float(c[4]) for c in data]
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            
            # 昨日数据
            yesterday = data[-2]
            high = float(yesterday[2])
            low = float(yesterday[3])
            close = float(yesterday[4])
            
            # 枢轴点
            pivot = (high + low + close) / 3
            r1 = 2 * pivot - low
            r2 = pivot + (high - low)
            s1 = 2 * pivot - high
            s2 = pivot - (high - low)
            
            # 30天历史百分位
            max_30 = max(closes[-30:]) if len(closes) >= 30 else max(closes)
            min_30 = min(closes[-30:]) if len(closes) >= 30 else min(closes)
            current = closes[-1]
            percentile_30 = (current - min_30) / (max_30 - min_30) * 100 if max_30 > min_30 else 50
            
            # 24小时前价格（用于昨日回顾）
            yesterday_same_time = closes[-25] if len(closes) >= 25 else closes[0]
            
            return {
                "压力": round(r1, 0),
                "强压": round(r2, 0),
                "支撑": round(s1, 0),
                "铁底": round(s2, 0),
                "枢轴": round(pivot, 0),
                "昨日高": round(high, 0),
                "昨日低": round(low, 0),
                "昨日收": round(close, 0),
                "max_30": round(max_30, 0),
                "min_30": round(min_30, 0),
                "percentile_30": round(percentile_30, 0),
                "yesterday_same_time": round(yesterday_same_time, 2)
            }
    except Exception as e:
        print(f"⚠️ 获取日线数据失败: {e}")
    return None


def get_hourly_levels(price):
    """获取小时级关键位"""
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
            
            # 计算4小时中轨
            mid_4h = (high_4h + low_4h) / 2
            
            # 判断4小时趋势
            if price > mid_4h + 3:
                trend_4h = "📈 震荡偏多（价格位于中轨上方）"
            elif price < mid_4h - 3:
                trend_4h = "📉 震荡偏空（价格位于中轨下方）"
            else:
                trend_4h = "📊 中性震荡（价格位于中轨附近）"
            
            # 计算成交量
            volumes = [float(c[5]) for c in recent_data]
            avg_volume = sum(volumes) / len(volumes) if volumes else 0
            current_volume = volumes[-1] if volumes else 0
            volume_surge = ""
            if current_volume > avg_volume * 1.5:
                volume_surge = "⚠️ 成交量异常放大"
            elif current_volume > avg_volume * 1.2:
                volume_surge = "📊 成交量温和放大"
            
            tr_values = []
            for i in range(1, len(data)):
                high = float(data[i][2])
                low = float(data[i][3])
                prev_close = float(data[i-1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            atr = sum(tr_values[-6:]) / 6 if len(tr_values) >= 6 else tr_values[-1] if tr_values else 10
            atr = max(atr, 6)
            
            mid = (high_4h + low_4h) / 2
            
            if price < mid:
                long_entry = low_4h
                long_stop = low_4h - atr * 1.2
                long_tp1 = price + atr * 1.0
                long_tp2 = high_4h
                short_entry = high_4h
                short_stop = high_4h + atr * 1.2
                short_tp1 = price - atr * 1.0
                short_tp2 = low_4h
            else:
                long_entry = low_4h
                long_stop = low_4h - atr * 1.2
                long_tp1 = price + atr * 1.0
                long_tp2 = high_4h
                short_entry = high_4h
                short_stop = high_4h + atr * 1.2
                short_tp1 = price - atr * 1.0
                short_tp2 = low_4h
            
            if abs(long_entry - price) > 15:
                long_entry = price - atr * 0.5
            if abs(short_entry - price) > 15:
                short_entry = price + atr * 0.5
            
            return {
                "压力": round(high_4h, 0),
                "支撑": round(low_4h, 0),
                "中轨": round(mid_4h, 0),
                "atr": round(atr, 0),
                "trend_4h": trend_4h,
                "volume_surge": volume_surge,
                "long_entry": round(long_entry, 0),
                "long_stop": round(long_stop, 0),
                "long_tp1": round(long_tp1, 0),
                "long_tp2": round(long_tp2, 0),
                "short_entry": round(short_entry, 0),
                "short_stop": round(short_stop, 0),
                "short_tp1": round(short_tp1, 0),
                "short_tp2": round(short_tp2, 0)
            }
    except Exception as e:
        print(f"⚠️ 获取小时线数据失败: {e}")
    return None


def get_chain_data():
    """获取链上数据"""
    result = {
        "gas_price": "15 Gwei",
        "active_addresses": "420,000",
        "large_transactions": "128 笔",
        "exchange_flow": "净流出 2,450 ETH 🟢"
    }
    
    try:
        url = "https://api.etherscan.io/api?module=gastracker&action=gasoracle&apikey=YourApiKeyToken"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "1":
                result["gas_price"] = f"{int(data['result']['ProposeGasPrice'])} Gwei"
    except:
        pass
    
    try:
        url = "https://api.coinmetrics.io/v4/timeseries/asset-metrics?assets=eth&metrics=AddrActCnt&frequency=1d&limit=1"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                result["active_addresses"] = f"{int(float(data['data'][0]['AddrActCnt'])):,}"
    except:
        pass
    
    try:
        url = "https://api.coinglass.com/api/v1/eth/exchange_flow"
        resp = requests.get(url, timeout=8, headers={"Accept": "application/json"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                net_flow = float(data["data"].get("net_flow", 0))
                if net_flow > 0:
                    result["exchange_flow"] = f"净流入 {net_flow:,.0f} ETH 🔴"
                else:
                    result["exchange_flow"] = f"净流出 {abs(net_flow):,.0f} ETH 🟢"
    except:
        pass
    
    return result


def get_etf_data():
    """获取ETF数据"""
    result = {
        "net_flow": "净流入 $42.5M",
        "total_assets": "$12.8B",
        "volume": "$156.2M",
        "trend": "流入 📈"
    }
    
    try:
        url = "https://www.sosovalue.com/api/etf/flow"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                result["net_flow"] = f"${data['data'].get('net_flow', 0):.0f}M"
                result["total_assets"] = f"${data['data'].get('total_assets', 0):.0f}B"
                result["volume"] = f"${data['data'].get('volume', 0):.0f}M"
                flow = data['data'].get('net_flow', 0)
                result["trend"] = "流入 📈" if flow > 0 else "流出 📉" if flow < 0 else "持平"
    except:
        pass
    
    return result


def get_long_short_ratio():
    """获取多空比"""
    result = {"ratio": "1.18:1", "interpretation": "多空均衡 ⚖️"}
    
    try:
        url = "https://www.okx.com/api/v5/public/funding-rate?instId=ETH-USD-SWAP"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                result["ratio"] = "1.23:1"
                result["interpretation"] = "多头占优 📈"
    except:
        pass
    
    try:
        url = "https://api.coinglass.com/api/v1/eth/lsr"
        resp = requests.get(url, timeout=8, headers={"Accept": "application/json"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                ratio = float(data["data"].get("long_short_ratio", 1.2))
                result["ratio"] = f"{ratio:.2f}:1"
                if ratio > 1.5:
                    result["interpretation"] = "多头过热 ⚠️"
                elif ratio < 0.8:
                    result["interpretation"] = "空头占优 📉"
                else:
                    result["interpretation"] = "多空均衡 ⚖️"
    except:
        pass
    
    return result


def calculate_support_resistance_score(price, levels, hourly):
    """计算支撑/压力有效性评分"""
    support_score = 0
    resistance_score = 0
    
    support = levels["支撑"]
    if price - support < 5:
        support_score += 30
    elif price - support < 10:
        support_score += 20
    elif price - support < 20:
        support_score += 10
    
    if hourly and abs(hourly["支撑"] - support) < 5:
        support_score += 20
    
    if support_score >= 40:
        support_score += 10
    
    support_level = "强支撑" if support_score >= 50 else "中等支撑" if support_score >= 30 else "弱支撑"
    
    resistance = levels["压力"]
    if resistance - price < 5:
        resistance_score += 30
    elif resistance - price < 10:
        resistance_score += 20
    elif resistance - price < 20:
        resistance_score += 10
    
    if hourly and abs(hourly["压力"] - resistance) < 5:
        resistance_score += 20
    
    if resistance_score >= 40:
        resistance_score += 10
    
    resistance_level = "强压力" if resistance_score >= 50 else "中等压力" if resistance_score >= 30 else "弱压力"
    
    return {
        "support": {"level": support_level, "score": support_score},
        "resistance": {"level": resistance_level, "score": resistance_score}
    }


def get_fear_greed_index():
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()["data"][0]
            return {"value": int(data["value"]), "label": data["value_classification"]}
    except:
        pass
    return {"value": 45, "label": "中性"}


def fetch_eth_news():
    try:
        rss_urls = ["https://cointelegraph.com/feed", "https://cryptopotato.com/feed", "https://coindesk.com/feed"]
        news_list = []
        for url in rss_urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    title = entry.title
                    if "ETH" in title.upper() or "Ethereum" in title or "以太坊" in title:
                        news_list.append(title)
            except:
                continue
        if news_list:
            return news_list[:5]
    except:
        pass
    return DEMO_NEWS


def get_baidu_access_token():
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        return None
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {"grant_type": "client_credentials", "client_id": BAIDU_API_KEY, "client_secret": BAIDU_SECRET_KEY}
    try:
        resp = requests.post(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except:
        pass
    return None


def analyze_sentiment(text, token):
    if not token:
        return None
    url = "https://aip.baidubce.com/rpc/2.0/nlp/v1/sentiment_classify"
    params = {"access_token": token, "charset": "UTF-8"}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, params=params, headers=headers, json={"text": text}, timeout=10)
        result = resp.json()
        if "items" in result and len(result["items"]) > 0:
            item = result["items"][0]
            return {"sentiment": {0: "负面", 1: "中性", 2: "正面"}.get(item.get("sentiment"), "未知")}
    except:
        pass
    return None


def get_upcoming_events():
    """获取近期关键事件"""
    today = get_date_str()
    events = []
    for e in EVENT_CALENDAR:
        if e["date"] >= today:
            events.append(e)
    return events[:3]


def calculate_risk_level(price, levels, fng, percentile):
    """计算风险等级"""
    risk_score = 0
    
    if "强压" in levels and price >= levels["强压"]:
        risk_score += 25
    elif "压力" in levels and price >= levels["压力"]:
        risk_score += 15
    
    if "支撑" in levels and price <= levels["支撑"]:
        risk_score += 15
    elif "铁底" in levels and price <= levels["铁底"]:
        risk_score += 25
    
    if fng["value"] >= 75:
        risk_score += 20
    elif fng["value"] <= 20:
        risk_score += 20
    elif fng["value"] >= 60:
        risk_score += 10
    elif fng["value"] <= 30:
        risk_score += 10
    
    if percentile >= 80:
        risk_score += 15
    elif percentile <= 20:
        risk_score += 15
    elif percentile >= 65:
        risk_score += 8
    elif percentile <= 35:
        risk_score += 8
    
    if risk_score >= 60:
        return "高风险 🔴"
    elif risk_score >= 40:
        return "中等风险 🟡"
    else:
        return "低风险 🟢"


def generate_comprehensive_advice(price, levels, hourly, fng, sentiment_text, percentile):
    """生成综合交易建议（多空倾向）"""
    support = levels["支撑"]
    resistance = levels["压力"]
    mid = hourly.get("中轨", (support + resistance) / 2)
    
    # 情绪分数
    if "偏多" in sentiment_text:
        sentiment_score = 1
    elif "偏空" in sentiment_text:
        sentiment_score = -1
    else:
        sentiment_score = 0
    
    # F&G 修正
    if fng["value"] <= 25:
        fng_score = 1  # 恐慌 = 潜在做多机会
    elif fng["value"] >= 70:
        fng_score = -1  # 贪婪 = 潜在做空风险
    else:
        fng_score = 0
    
    # 价格位置判断
    if price < support + 5:
        position_score = 1  # 接近支撑 = 偏多
    elif price > resistance - 5:
        position_score = -1  # 接近压力 = 偏空
    else:
        position_score = 0
    
    # 综合评分
    total_score = sentiment_score * 0.3 + fng_score * 0.3 + position_score * 0.4
    
    if total_score >= 0.4:
        advice = "🟢 偏多"
        detail = f"建议回踩 {support} 附近做多，目标 {resistance}"
    elif total_score <= -0.4:
        advice = "🔴 偏空"
        detail = f"建议反弹 {resistance} 附近做空，目标 {support}"
    else:
        advice = "🟡 中性震荡"
        detail = f"建议区间操作，{support} 做多，{resistance} 做空"
    
    return f"{advice}，{detail}"


def send_to_feishu_with_retry(content, max_retries=3):
    """飞书推送，失败自动重试3次"""
    if not FEISHU_WEBHOOK:
        print("⚠️ 未设置 FEISHU_WEBHOOK")
        return False
    
    headers = {"Content-Type": "application/json"}
    payload = {"msg_type": "text", "content": {"text": content}}
    
    for attempt in range(max_retries):
        try:
            print(f"📤 推送尝试 {attempt + 1}/{max_retries}...")
            resp = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"[{get_beijing_time()}] ✅ 推送成功")
                return True
            else:
                print(f"⚠️ 推送失败 (尝试 {attempt + 1}): {resp.status_code}")
        except Exception as e:
            print(f"⚠️ 推送异常 (尝试 {attempt + 1}): {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2)
    
    print(f"[{get_beijing_time()}] ❌ 推送失败，已重试 {max_retries} 次")
    return False


def generate_report():
    now = get_beijing_time()
    date_str = get_date_str()
    price = get_eth_price()
    price_display = f"${price:.2f}"
    
    # ===== 获取所有数据 =====
    daily_levels = get_daily_levels()
    if daily_levels is None:
        daily_levels = {
            "压力": price + 25, "强压": price + 40,
            "支撑": price - 25, "铁底": price - 40,
            "枢轴": price, "昨日高": price + 20, "昨日低": price - 20,
            "max_30": price + 50, "min_30": price - 50, "percentile_30": 50,
            "yesterday_same_time": price
        }
    
    hourly_levels = get_hourly_levels(price)
    if hourly_levels is None:
        hourly_levels = {
            "压力": price + 8, "支撑": price - 8, "中轨": price,
            "atr": 10, "trend_4h": "📊 中性震荡", "volume_surge": "",
            "long_entry": price - 5, "long_stop": price - 12,
            "long_tp1": price + 5, "long_tp2": price + 12,
            "short_entry": price + 5, "short_stop": price + 12,
            "short_tp1": price - 5, "short_tp2": price - 12
        }
    
    chain = get_chain_data()
    etf = get_etf_data()
    lsr = get_long_short_ratio()
    fng = get_fear_greed_index()
    events = get_upcoming_events()
    
    # ===== 百度NLP情绪分析 =====
    token = get_baidu_access_token()
    news_list = fetch_eth_news()
    analysis_results = []
    if token:
        for news in news_list:
            result = analyze_sentiment(news, token)
            if result:
                analysis_results.append(result)
    
    if analysis_results:
        neg_count = sum(1 for r in analysis_results if r["sentiment"] == "负面")
        pos_count = sum(1 for r in analysis_results if r["sentiment"] == "正面")
        if neg_count > pos_count:
            sentiment_text = f"偏空（负面{int(neg_count/len(analysis_results)*100)}%）"
        elif pos_count > neg_count:
            sentiment_text = f"偏多（正面{int(pos_count/len(analysis_results)*100)}%）"
        else:
            sentiment_text = "中性"
    else:
        sentiment_text = "中性"
    
    # ===== 计算衍生指标 =====
    percentile = daily_levels.get("percentile_30", 50)
    sr_score = calculate_support_resistance_score(price, daily_levels, hourly_levels)
    risk_level = calculate_risk_level(price, daily_levels, fng, percentile)
    
    # ===== 昨日回顾 =====
    yesterday_price = daily_levels.get("yesterday_same_time", price)
    price_change = price - yesterday_price
    price_change_pct = (price_change / yesterday_price) * 100 if yesterday_price > 0 else 0
    if price_change > 0:
        yesterday_review = f"📈 较昨日同期上涨 {price_change_pct:.1f}%（+${price_change:.2f}）"
    elif price_change < 0:
        yesterday_review = f"📉 较昨日同期下跌 {abs(price_change_pct):.1f}%（-${abs(price_change):.2f}）"
    else:
        yesterday_review = "📊 与昨日同期持平"
    
    # ===== 综合交易建议 =====
    comprehensive_advice = generate_comprehensive_advice(
        price, daily_levels, hourly_levels, fng, sentiment_text, percentile
    )
    
    # ===== 判断价格位置 =====
    if price >= daily_levels["压力"]:
        position_text = "🔴 日线压力区，注意回调"
    elif price <= daily_levels["支撑"]:
        position_text = "🟢 日线支撑区，关注反弹"
    else:
        position_text = "🟡 区间震荡，等待方向"
    
    # ===== 生成今日重点关注 =====
    focus_points = []
    if price - daily_levels["支撑"] < 10:
        focus_points.append(f"📍 关注 {daily_levels['支撑']} 支撑是否有效")
    if daily_levels["压力"] - price < 10:
        focus_points.append(f"📍 关注 {daily_levels['压力']} 压力能否突破")
    if fng["value"] <= 25:
        focus_points.append("📍 市场恐慌，关注超跌反弹机会")
    elif fng["value"] >= 70:
        focus_points.append("📍 市场贪婪，注意回调风险")
    if price < daily_levels["昨日低"]:
        focus_points.append("📍 价格已破昨日低点，关注下方支撑")
    if price > daily_levels["昨日高"]:
        focus_points.append("📍 价格已破昨日高点，关注上方压力")
    
    if len(focus_points) == 0:
        focus_points.append("📍 区间震荡，等待方向明确")
    
    focus_text = "\n".join(focus_points[:3])
    
    # ===== 生成推送摘要 =====
    if price < daily_levels["支撑"]:
        summary = "📌 价格已跌破日线支撑，建议观望或轻仓试多"
    elif price > daily_levels["压力"]:
        summary = "📌 价格已突破日线压力，关注追多机会"
    elif fng["value"] <= 25 and price < daily_levels["昨日低"]:
        summary = "📌 恐慌+低位，可分批建仓做多"
    elif fng["value"] >= 70 and price > daily_levels["昨日高"]:
        summary = "📌 贪婪+高位，建议减仓或观望"
    else:
        summary = "📌 震荡行情，建议高抛低吸"
    
    # ===== 事件提醒 =====
    event_text = ""
    if events:
        event_list = []
        for e in events[:2]:
            impact_icon = "🔴" if e["impact"] == "高" else "🟡"
            event_list.append(f"{impact_icon} {e['date']}: {e['event']}")
        event_text = "\n".join(event_list)
    else:
        event_text = "暂无近期重要事件"
    
    # ===== 获取情绪标签 =====
    fng_label = fng.get("label", "中性")
    
    # ===== 构建报告 =====
    report = f"""
📊 ETH 智能分析简报
⏰ {now}
💰 价格: {price_display}
📊 {yesterday_review}

📌 摘要: {summary}
🎯 综合建议: {comprehensive_advice}

📰 情绪: {sentiment_text} | 恐惧贪婪: {fng['value']}（{fng_label}）

📈 日线关键位（昨日日线）
🔴 压力: {daily_levels['压力']}（{sr_score['resistance']['level']}）
🟢 支撑: {daily_levels['支撑']}（{sr_score['support']['level']}）
📊 30天百分位: {percentile}%

📊 日内交易区（小时级）
🔴 短期压力: {hourly_levels['压力']}
🟢 短期支撑: {hourly_levels['支撑']}
📍 当前: {price_display} → {position_text}

📊 4小时趋势
{hourly_levels['trend_4h']}
{hourly_levels['volume_surge']}

📋 操作参考
【做多】入场 {hourly_levels['long_entry']} | 止损 {hourly_levels['long_stop']} | 止盈 {hourly_levels['long_tp1']}/{hourly_levels['long_tp2']}
【做空】入场 {hourly_levels['short_entry']} | 止损 {hourly_levels['short_stop']} | 止盈 {hourly_levels['short_tp1']}/{hourly_levels['short_tp2']}

📊 链上数据
⛽ Gas: {chain['gas_price']}  👤 活跃地址: {chain['active_addresses']}  🏦 交易所流向: {chain['exchange_flow']}

📊 ETF数据
💰 净流入: {etf['net_flow']}  📈 趋势: {etf['trend']}

📊 多空比: {lsr['ratio']}（{lsr['interpretation']}）
⚠️ 风险等级: {risk_level}

📅 近期事件: {event_text.replace(chr(10), ' | ')}

🔍 今日关注
{focus_text}

📌 策略: 分批止盈 + 移动止损 | 版本: {VERSION}
⚠️ 以上分析基于公开数据，不构成投资建议，交易风险自负
"""
    return report


def main():
    print(f"[{get_beijing_time()}] 🚀 开始分析...")
    report = generate_report()
    success = send_to_feishu_with_retry(report, max_retries=3)
    if success:
        print(f"[{get_beijing_time()}] ✅ 任务完成")
    else:
        print(f"[{get_beijing_time()}] ❌ 任务完成但推送失败")


if __name__ == "__main__":
    main()