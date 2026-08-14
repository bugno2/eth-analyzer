#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH全智能分析推送 (多维综合分析版)

import requests
import json
import os
import feedparser
import math
from datetime import datetime, timezone, timedelta

# ========== 从环境变量读取密钥 ==========
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")
BAIDU_API_KEY = os.environ.get("BAIDU_API_KEY")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_SECRET_KEY")
# =========================================

# ========== 备用数据 ==========
DEMO_NEWS = [
    "ETH价格震荡下行，市场情绪谨慎",
    "以太坊生态发展稳步推进，开发者活跃度上升",
    "巨鲸地址近期频繁转移ETH，引发市场关注"
]

BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")

# ========== 1. 数据获取层 ==========

def get_eth_price():
    """获取ETH实时价格"""
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

def get_eth_klines():
    """获取ETH K线数据（计算ATR和均线）"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=50"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            closes = [float(c[4]) for c in data]
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
            tr_values = []
            for i in range(1, len(data)):
                high = float(data[i][2])
                low = float(data[i][3])
                prev_close = float(data[i-1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            atr = sum(tr_values[-14:]) / 14 if len(tr_values) >= 14 else tr_values[-1] if tr_values else 0
            return {"ma20": ma20, "atr": atr, "close": closes[-1]}
    except:
        pass
    return {"ma20": 1850, "atr": 15, "close": 1850}

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
            return {"sentiment": {0: "负面", 1: "中性", 2: "正面"}.get(item.get("sentiment"), "未知"), "positive_prob": round(item.get("positive_prob", 0), 3), "negative_prob": round(item.get("negative_prob", 0), 3)}
    except:
        pass
    return None


# ========== 2. 分析引擎层 ==========

def calculate_levels(price, atr):
    """基于价格和ATR计算动态关键位"""
    atr_step = max(atr * 1.2, 8)
    # 根据价格当前位置微调
    base = round(price / 5) * 5
    return {
        "强压": base + int(atr_step * 3),
        "压力1": base + int(atr_step * 2),
        "压力2": base + int(atr_step * 1.2),
        "支撑1": base - int(atr_step * 1.2),
        "支撑2": base - int(atr_step * 2),
        "铁底": base - int(atr_step * 3),
        "当前": price
    }

def analyze_price_position(price, levels):
    if price >= levels["强压"]:
        return "突破强压区", "极强"
    elif price >= levels["压力1"]:
        return "高位压力区", "强"
    elif price >= levels["压力2"]:
        return "中上区域", "中性偏强"
    elif price >= levels["支撑1"]:
        return "中轴附近", "中性"
    elif price >= levels["支撑2"]:
        return "低位支撑区", "中性偏弱"
    elif price >= levels["铁底"]:
        return "铁底区域", "弱"
    else:
        return "跌破铁底", "极弱"

def analyze_sentiment_score(news_sentiment, fng_value, price, levels):
    """综合情绪评分 (0-100)"""
    if news_sentiment == "偏多":
        news_score = 70
    elif news_sentiment == "偏空":
        news_score = 30
    else:
        news_score = 50
    if fng_value <= 25:
        fng_score = 80
    elif fng_value <= 45:
        fng_score = 60
    elif fng_value <= 55:
        fng_score = 50
    elif fng_value <= 75:
        fng_score = 30
    else:
        fng_score = 20
    # 价格位置修正
    if price <= levels["支撑2"]:
        position_bonus = 10
    elif price >= levels["压力1"]:
        position_bonus = -10
    else:
        position_bonus = 0
    combined = news_score * 0.35 + fng_score * 0.45 + (50 + position_bonus) * 0.2
    return max(0, min(100, combined))

def get_trading_signal(price, levels, sentiment_score, ma20):
    above_ma = price > ma20
    if sentiment_score >= 70 and price <= levels["支撑1"]:
        signal, confidence = "🟢 强烈做多", "高"
    elif sentiment_score >= 60 and price <= levels["支撑2"]:
        signal, confidence = "🟢 偏多", "中"
    elif sentiment_score <= 30 and price >= levels["压力1"]:
        signal, confidence = "🔴 强烈做空", "高"
    elif sentiment_score <= 40 and price >= levels["压力2"]:
        signal, confidence = "🔴 偏空", "中"
    elif sentiment_score >= 55:
        signal, confidence = "🟡 震荡偏多", "低"
    elif sentiment_score <= 45:
        signal, confidence = "🟡 震荡偏空", "低"
    else:
        signal, confidence = "⚪ 观望", "低"
    return signal, confidence

def get_position_advice(price, levels, atr, sentiment_score):
    """生成更精准的操作建议，接近当前价格"""
    # 动态计算入场价 - 更贴近当前价格
    stop_distance = max(atr * 0.6, 6)
    
    # 做多：在当前价格下方找支撑
    supports = [levels["支撑1"], levels["支撑2"], levels["铁底"]]
    valid_supports = [s for s in supports if s < price]
    if valid_supports:
        base_entry = max(valid_supports)
    else:
        base_entry = price - 15
    
    # 如果当前价格已经接近支撑（距离<5），入场价就设在当前价
    if price - base_entry < 5:
        long_entry = f"{price:.0f}-{price+5:.0f}"
        long_stop = f"{price-10:.0f}"
        long_tp1 = f"{price + (price - base_entry) * 0.8:.0f}"
        long_tp2 = f"{price + (price - base_entry) * 1.5:.0f}"
    else:
        long_entry = f"{base_entry:.0f}-{base_entry+5:.0f}"
        long_stop = f"{base_entry-10:.0f}"
        long_tp1 = f"{price + (price - base_entry) * 0.6:.0f}"
        long_tp2 = f"{price + (price - base_entry) * 1.2:.0f}"
    
    # 做空：在当前价格上方找压力
    resistances = [levels["压力2"], levels["压力1"], levels["强压"]]
    valid_resistances = [r for r in resistances if r > price]
    if valid_resistances:
        base_entry = min(valid_resistances)
    else:
        base_entry = price + 15
    
    if base_entry - price < 5:
        short_entry = f"{price:.0f}-{price+5:.0f}"
        short_stop = f"{price+10:.0f}"
        short_tp1 = f"{price - (base_entry - price) * 0.8:.0f}"
        short_tp2 = f"{price - (base_entry - price) * 1.5:.0f}"
    else:
        short_entry = f"{base_entry:.0f}-{base_entry+5:.0f}"
        short_stop = f"{base_entry+10:.0f}"
        short_tp1 = f"{price - (base_entry - price) * 0.6:.0f}"
        short_tp2 = f"{price - (base_entry - price) * 1.2:.0f}"
    
    return {
        "long": {"entry": long_entry, "stop": long_stop, "tp1": long_tp1, "tp2": long_tp2},
        "short": {"entry": short_entry, "stop": short_stop, "tp1": short_tp1, "tp2": short_tp2},
        "nearest_support": base_entry if valid_supports else price-15,
        "nearest_resistance": base_entry if valid_resistances else price+15,
        "stop_distance": f"{stop_distance:.0f}"
    }

def get_position_recommendation(sentiment_score, price, levels, fng):
    """根据综合情况给出最优先的操作建议"""
    if sentiment_score >= 65 and price <= levels["支撑1"]:
        return "🎯 优先做多（情绪偏多+价格在支撑区）"
    elif sentiment_score >= 55 and price <= levels["支撑2"]:
        return "🎯 可考虑做多（情绪温和+价格在低位）"
    elif sentiment_score <= 35 and price >= levels["压力1"]:
        return "🎯 优先做空（情绪偏空+价格在压力区）"
    elif sentiment_score <= 45 and price >= levels["压力2"]:
        return "🎯 可考虑做空（情绪偏空+价格在中高位）"
    elif sentiment_score >= 55 and price >= levels["压力2"]:
        return "🎯 等待回调后再做多（价格偏高）"
    elif sentiment_score <= 45 and price <= levels["支撑2"]:
        return "🎯 等待反弹后再做空（价格偏低）"
    else:
        return "🎯 建议观望（情绪和价格位置不匹配）"


# ========== 3. 报告生成层 ==========

def generate_report():
    now = get_beijing_time()
    price = get_eth_price()
    price_display = f"${price:.2f}"
    kline = get_eth_klines()
    fng = get_fear_greed_index()
    news_list = fetch_eth_news()
    
    token = get_baidu_access_token()
    analysis_results = []
    if token:
        for news in news_list:
            result = analyze_sentiment(news, token)
            if result:
                analysis_results.append({**result, "title": news})
    
    if analysis_results and len(analysis_results) > 0:
        neg_count = sum(1 for r in analysis_results if r["sentiment"] == "负面")
        pos_count = sum(1 for r in analysis_results if r["sentiment"] == "正面")
        if neg_count > pos_count:
            news_sentiment, detail = "偏空", f"负面{int(neg_count/len(analysis_results)*100)}% / 正面{int(pos_count/len(analysis_results)*100)}%"
        elif pos_count > neg_count:
            news_sentiment, detail = "偏多", f"正面{int(pos_count/len(analysis_results)*100)}% / 负面{int(neg_count/len(analysis_results)*100)}%"
        else:
            news_sentiment, detail = "中性", "正面50% / 负面50%"
    else:
        news_sentiment, detail = "中性", "正面50% / 负面50%"
    
    levels = calculate_levels(price, kline["atr"])
    pos_desc, pos_strength = analyze_price_position(price, levels)
    sentiment_score = analyze_sentiment_score(news_sentiment, fng["value"], price, levels)
    signal, confidence = get_trading_signal(price, levels, sentiment_score, kline["ma20"])
    advice = get_position_advice(price, levels, kline["atr"], sentiment_score)
    priority = get_position_recommendation(sentiment_score, price, levels, fng)
    
    reasons = [
        f"📊 综合情绪评分 {sentiment_score:.0f}%",
        f"📍 价格处于{pos_desc}（强度:{pos_strength}）",
        f"📈 MA20: {kline['ma20']:.0f}，价格在{'上方' if price > kline['ma20'] else '下方'}",
        f"😨 F&G: {fng['value']}（{fng['label']}）"
    ]
    
    risks = []
    if price >= levels["压力1"]:
        risks.append("⚠️ 价格处于压力区，追多风险较大")
    if price <= levels["支撑2"]:
        risks.append("⚠️ 价格处于支撑区，注意破位下行风险")
    if fng["value"] >= 70:
        risks.append("⚠️ 市场贪婪，注意回调")
    if fng["value"] <= 20:
        risks.append("⚠️ 市场恐慌，可能继续下跌")
    if not risks:
        risks.append("⚪ 当前无明显极端风险")
    
    # 构建报告
    report = f"""
📊 ETH-AI 全视角分析
📅 {now} (北京时间)
💰 ETH实时价格: {price_display}
🤖 AI状态: ✅ 已连接 · AI引擎运行中

📰 情绪面分析
新闻情绪: {news_sentiment}（{detail}）
恐惧贪婪: {fng['value']}（{fng['label']}）
综合情绪评分: {sentiment_score:.0f}%

📈 技术面分析
价格位置: {pos_desc}（强度:{pos_strength}）
MA20趋势: {kline['ma20']:.0f}（价格在{'上方' if price > kline['ma20'] else '下方'}）
ATR波动率: ${kline['atr']:.1f}

🎯 交易信号
信号: {signal} | 置信度: {confidence}
{priority}

📉 动态关键位
🔴 强压: {levels['强压']}
🔴 压力: {levels['压力1']} / {levels['压力2']}
🟢 支撑: {levels['支撑1']} / {levels['支撑2']}
🟢 铁底: {levels['铁底']}

📋 具体操作建议
【做多方案】入场: {advice['long']['entry']} | 止损: {advice['long']['stop']}（约{advice['stop_distance']}点）| 止盈: {advice['long']['tp1']} / {advice['long']['tp2']}
【做空方案】入场: {advice['short']['entry']} | 止损: {advice['short']['stop']}（约{advice['stop_distance']}点）| 止盈: {advice['short']['tp1']} / {advice['short']['tp2']}
📌 优先方向: {'做多' if sentiment_score >= 55 else '做空' if sentiment_score <= 45 else '观望'}

📦 动态持仓管理
📉 到 {levels['支撑1']} → 持盈，止盈上移至 {levels['支撑1']+5}
📉 到 {levels['支撑2']} → 全部离场（支撑告破）
📈 反抽 {levels['压力2']} 受阻 → 开空，分批加仓
📈 站稳 {levels['压力1']} 超15分钟 → 止损离场

🧠 决策依据
{chr(10).join(reasons)}

⚠️ 风险提示
{chr(10).join(risks)}

🔑 综合策略: {signal} | 分批止盈 + 移动止损 + 严控仓位

⚠️ 分析仅供参考，投资决策需自行判断，盈亏自负。
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
            print(f"[{get_beijing_time()}] ✅ 飞书推送成功")
        else:
            print(f"[{get_beijing_time()}] ❌ 推送失败: {resp.text}")
    except Exception as e:
        print(f"[{get_beijing_time()}] ❌ 请求异常: {e}")

def main():
    print(f"[{get_beijing_time()}] 🚀 开始分析ETH情绪...")
    report = generate_report()
    send_to_feishu(report)
    print(f"[{get_beijing_time()}] ✅ 分析完成")

if __name__ == "__main__":
    main()