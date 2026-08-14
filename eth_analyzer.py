#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH智能分析推送 (精简优化版)

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

def get_detailed_klines():
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=50"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            closes = [float(c[4]) for c in data]
            
            recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
            recent_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)
            short_high = max(highs[-5:]) if len(highs) >= 5 else max(highs)
            short_low = min(lows[-5:]) if len(lows) >= 5 else min(lows)
            
            tr_values = []
            for i in range(1, len(data)):
                high = float(data[i][2])
                low = float(data[i][3])
                prev_close = float(data[i-1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            atr = sum(tr_values[-14:]) / 14 if len(tr_values) >= 14 else tr_values[-1] if tr_values else 10
            
            return {
                "recent_high": recent_high, "recent_low": recent_low,
                "short_high": short_high, "short_low": short_low,
                "atr": atr,
                "ma20": sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
            }
    except:
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


# ========== 分析引擎 ==========

def calculate_levels(price, kline):
    atr = max(kline["atr"], 8)
    
    # 支撑位：取近期低点或短期低点
    support_candidates = [s for s in [kline["short_low"], kline["recent_low"]] if s < price]
    support_1 = max(support_candidates) if support_candidates else price - atr * 0.8
    
    # 压力位：取近期高点或短期高点
    resistance_candidates = [r for r in [kline["short_high"], kline["recent_high"]] if r > price]
    resistance_1 = min(resistance_candidates) if resistance_candidates else price + atr * 0.8
    
    return {
        "压力": int(resistance_1),
        "支撑": int(support_1),
        "atr": int(atr)
    }

def get_position_advice(price, levels):
    """生成简洁的操作建议"""
    atr = levels["atr"]
    support = levels["支撑"]
    resistance = levels["压力"]
    
    # 做多建议
    if price <= support + 3:
        long_entry = f"{price:.0f}"
        long_stop = f"{price - atr * 1.5:.0f}"
    else:
        long_entry = f"{support:.0f}"
        long_stop = f"{support - atr * 1.5:.0f}"
    
    long_tp1 = f"{int(float(long_entry) + atr * 1.5)}"
    long_tp2 = f"{int(float(long_entry) + atr * 2.5)}"
    
    # 做空建议
    if price >= resistance - 3:
        short_entry = f"{price:.0f}"
        short_stop = f"{price + atr * 1.5:.0f}"
    else:
        short_entry = f"{resistance:.0f}"
        short_stop = f"{resistance + atr * 1.5:.0f}"
    
    short_tp1 = f"{int(float(short_entry) - atr * 1.5)}"
    short_tp2 = f"{int(float(short_entry) - atr * 2.5)}"
    
    return {
        "long": {"entry": long_entry, "stop": long_stop, "tp1": long_tp1, "tp2": long_tp2},
        "short": {"entry": short_entry, "stop": short_stop, "tp1": short_tp1, "tp2": short_tp2}
    }


# ========== 报告生成 ==========

def generate_report():
    now = get_beijing_time()
    price = get_eth_price()
    price_display = f"${price:.2f}"
    
    kline = get_detailed_klines()
    if kline is None:
        kline = {"recent_high": 1880, "recent_low": 1840, "short_high": 1870, "short_low": 1855, "atr": 15, "ma20": 1860}
    
    fng = get_fear_greed_index()
    news_list = fetch_eth_news()
    
    # 百度NLP分析
    token = get_baidu_access_token()
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
    
    levels = calculate_levels(price, kline)
    advice = get_position_advice(price, levels)
    
    # 判断当前价格位置
    if price >= levels["压力"]:
        position_text = "🔴 压力区，注意回调"
    elif price <= levels["支撑"]:
        position_text = "🟢 支撑区，关注反弹"
    else:
        position_text = "🟡 区间震荡，等待方向"
    
    # 构建精简报告
    report = f"""
📊 ETH 智能分析简报
⏰ {now}
💰 价格: {price_display}

📰 情绪: {sentiment_text} | 恐惧贪婪: {fng['value']}（{fng['label']}）

📈 关键位
🔴 压力: {levels['压力']}
🟢 支撑: {levels['支撑']}
📍 当前: {price_display} → {position_text}

📋 操作参考
【做多】入场 {advice['long']['entry']} | 止损 {advice['long']['stop']} | 止盈 {advice['long']['tp1']}/{advice['long']['tp2']}
【做空】入场 {advice['short']['entry']} | 止损 {advice['short']['stop']} | 止盈 {advice['short']['tp1']}/{advice['short']['tp2']}

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
            print(f"[{get_beijing_time()}] ❌ 推送失败")
    except Exception as e:
        print(f"[{get_beijing_time()}] ❌ 异常: {e}")

def main():
    print(f"[{get_beijing_time()}] 🚀 开始分析...")
    report = generate_report()
    send_to_feishu(report)
    print(f"[{get_beijing_time()}] ✅ 完成")

if __name__ == "__main__":
    main()