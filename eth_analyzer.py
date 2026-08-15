#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH智能分析推送 (两级关键位版)

import requests
import json
import os
import feedparser
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

def get_beijing_time():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


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
    """获取日线级关键位（基于昨日日线，全天不变，看大方向）"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1d&limit=2"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) >= 2:
                yesterday = data[-2]
                high = float(yesterday[2])
                low = float(yesterday[3])
                close = float(yesterday[4])
                
                pivot = (high + low + close) / 3
                r1 = 2 * pivot - low
                r2 = pivot + (high - low)
                s1 = 2 * pivot - high
                s2 = pivot - (high - low)
                
                return {
                    "压力": round(r1, 0),
                    "强压": round(r2, 0),
                    "支撑": round(s1, 0),
                    "铁底": round(s2, 0),
                    "枢轴": round(pivot, 0),
                    "昨日高": round(high, 0),
                    "昨日低": round(low, 0)
                }
    except Exception as e:
        print(f"⚠️ 获取日线数据失败: {e}")
    return None


def get_hourly_levels(price):
    """获取小时级关键位（基于4小时K线，动态更新，定入场）"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=10"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            
            # 取最近6根K线（不含当前未完成的）
            recent_data = data[-7:-1] if len(data) >= 7 else data[:-1]
            if not recent_data:
                recent_data = data[-6:] if len(data) >= 6 else data
            
            highs = [float(c[2]) for c in recent_data]
            lows = [float(c[3]) for c in recent_data]
            
            high_4h = max(highs) if highs else price + 10
            low_4h = min(lows) if lows else price - 10
            
            # 计算ATR
            tr_values = []
            for i in range(1, len(data)):
                high = float(data[i][2])
                low = float(data[i][3])
                prev_close = float(data[i-1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            atr = sum(tr_values[-6:]) / 6 if len(tr_values) >= 6 else tr_values[-1] if tr_values else 10
            atr = max(atr, 6)
            
            # 计算入场位（贴近当前价格）
            mid = (high_4h + low_4h) / 2
            
            if price < mid:
                # 价格在中轴下方，偏多思路
                long_entry = low_4h
                long_stop = low_4h - atr * 1.2
                long_tp1 = price + atr * 1.0
                long_tp2 = high_4h
                short_entry = high_4h
                short_stop = high_4h + atr * 1.2
                short_tp1 = price - atr * 1.0
                short_tp2 = low_4h
            else:
                # 价格在中轴上方，偏空思路
                long_entry = low_4h
                long_stop = low_4h - atr * 1.2
                long_tp1 = price + atr * 1.0
                long_tp2 = high_4h
                short_entry = high_4h
                short_stop = high_4h + atr * 1.2
                short_tp1 = price - atr * 1.0
                short_tp2 = low_4h
            
            # 如果入场价离当前价太远（超过15点），调整到当前价附近
            if abs(long_entry - price) > 15:
                long_entry = price - atr * 0.5
            if abs(short_entry - price) > 15:
                short_entry = price + atr * 0.5
            
            return {
                "压力": round(high_4h, 0),
                "支撑": round(low_4h, 0),
                "atr": round(atr, 0),
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


# ========== 报告生成 ==========

def generate_report():
    now = get_beijing_time()
    price = get_eth_price()
    price_display = f"${price:.2f}"
    
    # 1. 获取日线级关键位（稳定，看方向）
    daily_levels = get_daily_levels()
    if daily_levels is None:
        daily_levels = {"压力": price + 25, "支撑": price - 25, "昨日高": price + 20, "昨日低": price - 20}
    
    # 2. 获取小时级关键位（动态，定入场）
    hourly_levels = get_hourly_levels(price)
    if hourly_levels is None:
        hourly_levels = {
            "压力": price + 8, "支撑": price - 8,
            "long_entry": price - 5, "long_stop": price - 12,
            "long_tp1": price + 5, "long_tp2": price + 12,
            "short_entry": price + 5, "short_stop": price + 12,
            "short_tp1": price - 5, "short_tp2": price - 12
        }
    
    # 3. 获取情绪数据
    fng = get_fear_greed_index()
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
    
    # 4. 判断当前价格位置
    daily_support = daily_levels["支撑"]
    daily_resistance = daily_levels["压力"]
    
    if price >= daily_resistance:
        position_text = "🔴 日线压力区，注意回调"
    elif price <= daily_support:
        position_text = "🟢 日线支撑区，关注反弹"
    else:
        position_text = "🟡 区间震荡，等待方向"
    
    # 5. 计算日内位置百分比
    range_high = daily_levels.get("昨日高", daily_resistance)
    range_low = daily_levels.get("昨日低", daily_support)
    if range_high > range_low:
        position_pct = (price - range_low) / (range_high - range_low) * 100
        position_pct_text = f"（日内位置：{position_pct:.0f}%）"
    else:
        position_pct_text = ""
    
    # 6. 构建报告
    report = f"""
📊 ETH 智能分析简报
⏰ {now}
💰 价格: {price_display} {position_pct_text}

📰 情绪: {sentiment_text} | 恐惧贪婪: {fng['value']}（{fng['label']}）

📈 今日大方向（日线级，全天有效）
🔴 日线压力: {daily_levels['压力']}
🟢 日线支撑: {daily_levels['支撑']}

📊 日内交易区（小时级，动态更新）
🔴 短期压力: {hourly_levels['压力']}
🟢 短期支撑: {hourly_levels['支撑']}
📍 当前: {price_display} → {position_text}

📋 操作参考（入场位贴近当前价）
【做多】入场 {hourly_levels['long_entry']} | 止损 {hourly_levels['long_stop']} | 止盈 {hourly_levels['long_tp1']}/{hourly_levels['long_tp2']}
【做空】入场 {hourly_levels['short_entry']} | 止损 {hourly_levels['short_stop']} | 止盈 {hourly_levels['short_tp1']}/{hourly_levels['short_tp2']}

📌 策略: 分批止盈 + 移动止损
⚠️ 仅供参考，风险自担
"""
    return report


def send_to_feishu(content):
    if not FEISHU_WEBHOOK:
        print("⚠️ 未设置 FEISHU_WEBHOOK")
        return
    headers = {"Content-Type": "application/json"}
    payload = {"msg_type": "text", "content": {"text": content}}
    try:
        resp = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[{get_beijing_time()}] ✅ 推送成功")
        else:
            print(f"[{get_beijing_time()}] ❌ 推送失败: {resp.text}")
    except Exception as e:
        print(f"[{get_beijing_time()}] ❌ 异常: {e}")


def main():
    print(f"[{get_beijing_time()}] 🚀 开始分析...")
    report = generate_report()
    send_to_feishu(report)
    print(f"[{get_beijing_time()}] ✅ 完成")


if __name__ == "__main__":
    main()