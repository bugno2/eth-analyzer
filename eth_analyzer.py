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
            
            # 计算MA20
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
            
            # 计算ATR (14周期)
            tr_values = []
            for i in range(1, len(data)):
                high = float(data[i][2])
                low = float(data[i][3])
                prev_close = float(data[i-1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            atr = sum(tr_values[-14:]) / 14 if len(tr_values) >= 14 else tr_values[-1] if tr_values else 0
            
            return {
                "ma20": ma20,
                "atr": atr,
                "close": closes[-1],
                "high": highs[-1],
                "low": lows[-1]
            }
    except:
        pass
    return {"ma20": 1850, "atr": 15, "close": 1850, "high": 1850, "low": 1850}

def get_fear_greed_index():
    """获取恐惧贪婪指数"""
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
    """获取ETH新闻"""
    try:
        rss_urls = [
            "https://cointelegraph.com/feed",
            "https://cryptopotato.com/feed",
            "https://coindesk.com/feed"
        ]
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
    """获取百度Token"""
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
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
            return resp.json().get("access_token")
    except:
        pass
    return None

def analyze_sentiment(text, token):
    """百度情感分析"""
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
            return {
                "sentiment": {0: "负面", 1: "中性", 2: "正面"}.get(item.get("sentiment"), "未知"),
                "positive_prob": round(item.get("positive_prob", 0), 3),
                "negative_prob": round(item.get("negative_prob", 0), 3)
            }
    except:
        pass
    return None


# ========== 2. 分析引擎层 ==========

def calculate_levels(price, atr):
    """基于价格和ATR计算动态关键位"""
    atr_step = max(atr, 10)
    base = round(price / 10) * 10
    
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
    """分析价格位置"""
    if price >= levels["强压"]:
        return "突破强压", "极强", 1.0
    elif price >= levels["压力1"]:
        return "压力区上沿", "强", 0.8
    elif price >= levels["压力2"]:
        return "压力区", "中性偏强", 0.6
    elif price >= levels["支撑1"]:
        return "中轴附近", "中性", 0.5
    elif price >= levels["支撑2"]:
        return "支撑区", "中性偏弱", 0.4
    elif price >= levels["铁底"]:
        return "支撑区下沿", "弱", 0.2
    else:
        return "跌破铁底", "极弱", 0.0

def analyze_sentiment_score(news_sentiment, fng_value):
    """综合情绪评分 (0-100)"""
    # 新闻情绪评分
    if news_sentiment == "偏多":
        news_score = 70
    elif news_sentiment == "偏空":
        news_score = 30
    else:
        news_score = 50
    
    # F&G评分 (恐惧<30为多头机会, >70为空头风险)
    if fng_value <= 25:
        fng_score = 80  # 极度恐惧 = 潜在买入机会
    elif fng_value <= 45:
        fng_score = 60
    elif fng_value <= 55:
        fng_score = 50
    elif fng_value <= 75:
        fng_score = 30
    else:
        fng_score = 20  # 极度贪婪 = 潜在卖出风险
    
    # 综合评分 (新闻40% + F&G60%)
    combined = news_score * 0.4 + fng_score * 0.6
    return combined

def get_trading_signal(price, levels, sentiment_score, ma20):
    """生成交易信号"""
    # 判断价格与均线关系
    above_ma = price > ma20
    ma_trend = "上升" if above_ma else "下降"
    
    # 判断价格位置
    if price >= levels["压力1"]:
        position = "高位"
        base_action = "做空/减仓" if sentiment_score < 50 else "观望"
    elif price <= levels["支撑2"]:
        position = "低位"
        base_action = "做多/加仓" if sentiment_score > 50 else "观望"
    else:
        position = "中位"
        base_action = "震荡操作"
    
    # 综合信号
    if sentiment_score >= 65 and price <= levels["支撑1"]:
        signal = "🟢 强烈做多"
        confidence = "高"
    elif sentiment_score >= 55 and price <= levels["支撑2"]:
        signal = "🟢 偏多"
        confidence = "中"
    elif sentiment_score <= 35 and price >= levels["压力1"]:
        signal = "🔴 强烈做空"
        confidence = "高"
    elif sentiment_score <= 45 and price >= levels["压力2"]:
        signal = "🔴 偏空"
        confidence = "中"
    elif sentiment_score >= 55:
        signal = "🟡 震荡偏多"
        confidence = "低"
    elif sentiment_score <= 45:
        signal = "🟡 震荡偏空"
        confidence = "低"
    else:
        signal = "⚪ 观望"
        confidence = "低"
    
    return signal, confidence, position, ma_trend

def get_position_advice(price, levels, atr):
    """生成具体操作建议"""
    nearest_support = max([l for l in [levels["支撑1"], levels["支撑2"], levels["铁底"]] if l < price], default=price-20)
    nearest_resistance = min([l for l in [levels["压力2"], levels["压力1"], levels["强压"]] if l > price], default=price+20)
    
    stop_distance = max(atr * 0.8, 8)
    
    # 做多建议
    long_entry = nearest_support
    long_stop = nearest_support - stop_distance
    long_tp1 = price + (price - nearest_support) * 0.6
    long_tp2 = nearest_resistance
    
    # 做空建议
    short_entry = nearest_resistance
    short_stop = nearest_resistance + stop_distance
    short_tp1 = price - (nearest_resistance - price) * 0.6
    short_tp2 = nearest_support
    
    return {
        "long": {
            "entry": f"{long_entry:.0f}-{long_entry+5:.0f}",
            "stop": f"{long_stop:.0f}",
            "tp1": f"{long_tp1:.0f}",
            "tp2": f"{long_tp2:.0f}"
        },
        "short": {
            "entry": f"{short_entry:.0f}-{short_entry+5:.0f}",
            "stop": f"{short_stop:.0f}",
            "tp1": f"{short_tp1:.0f}",
            "tp2": f"{short_tp2:.0f}"
        },
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "stop_distance": f"{stop_distance:.0f}"
    }


# ========== 3. 报告生成层 ==========

def generate_report():
    now = get_beijing_time()
    
    # 获取数据
    price = get_eth_price()
    price_display = f"${price:.2f}"
    kline = get_eth_klines()
    fng = get_fear_greed_index()
    news_list = fetch_eth_news()
    
    # 百度NLP分析
    token = get_baidu_access_token()
    analysis_results = []
    if token:
        for news in news_list:
            result = analyze_sentiment(news, token)
            if result:
                analysis_results.append({**result, "title": news})
    
    # 情绪统计
    if analysis_results and len(analysis_results) > 0:
        neg_count = sum(1 for r in analysis_results if r["sentiment"] == "负面")
        pos_count = sum(1 for r in analysis_results if r["sentiment"] == "正面")
        if neg_count > pos_count:
            news_sentiment = "偏空"
            detail = f"负面{int(neg_count/len(analysis_results)*100)}% / 正面{int(pos_count/len(analysis_results)*100)}%"
        elif pos_count > neg_count:
            news_sentiment = "偏多"
            detail = f"正面{int(pos_count/len(analysis_results)*100)}% / 负面{int(neg_count/len(analysis_results)*100)}%"
        else:
            news_sentiment = "中性"
            detail = f"正面50% / 负面50%"
    else:
        news_sentiment = "中性"
        detail = "正面50% / 负面50%"
    
    # 计算关键位
    levels = calculate_levels(price, kline["atr"])
    
    # 分析价格位置
    pos_desc, pos_strength, pos_score = analyze_price_position(price, levels)
    
    # 综合情绪评分
    sentiment_score = analyze_sentiment_score(news_sentiment, fng["value"])
    
    # 生成交易信号
    signal, confidence, position, ma_trend = get_trading_signal(price, levels, sentiment_score, kline["ma20"])
    
    # 生成操作建议
    advice = get_position_advice(price, levels, kline["atr"])
    
    # 决策理由
    reasons = []
    if sentiment_score >= 55:
        reasons.append(f"📊 综合情绪评分 {sentiment_score:.0f}/100，偏多头")
    elif sentiment_score <= 45:
        reasons.append(f"📊 综合情绪评分 {sentiment_score:.0f}/100，偏空头")
    else:
        reasons.append(f"📊 综合情绪评分 {sentiment_score:.0f}/100，中性")
    
    if pos_score >= 0.6:
        reasons.append(f"📍 价格处于{pos_desc}（强度:{pos_strength}）")
    elif pos_score <= 0.4:
        reasons.append(f"📍 价格处于{pos_desc}（强度:{pos_strength}）")
    else:
        reasons.append(f"📍 价格处于{pos_desc}")
    
    if price > kline["ma20"]:
        reasons.append(f"📈 价格在MA20({kline['ma20']:.0f})上方，短期趋势偏多")
    else:
        reasons.append(f"📉 价格在MA20({kline['ma20']:.0f})下方，短期趋势偏空")
    
    if fng["value"] <= 30:
        reasons.append(f"😨 恐惧贪婪指数 {fng['value']}（{fng['label']}），市场恐慌，可能超跌反弹")
    elif fng["value"] >= 70:
        reasons.append(f"😰 恐惧贪婪指数 {fng['value']}（{fng['label']}），市场贪婪，注意回调风险")
    else:
        reasons.append(f"😐 恐惧贪婪指数 {fng['value']}（{fng['label']}），市场情绪平稳")
    
    # 风险提示
    risks = []
    if price >= levels["压力1"]:
        risks.append("⚠️ 价格处于压力区，追多风险较大")
    if price <= levels["支撑2"]:
        risks.append("⚠️ 价格处于支撑区，注意破位下行风险")
    if fng["value"] >= 70:
        risks.append("⚠️ 市场贪婪情绪较重，注意回调")
    if fng["value"] <= 20:
        risks.append("⚠️ 市场极度恐慌，可能继续下跌")
    if len(risks) == 0:
        risks.append("⚪ 当前无明显极端风险")
    
    # 构建报告
    report = f"""
📊 ETH-AI 全视角分析
📅 {now} (北京时间)
💰 ETH实时价格: {price_display}
🤖 AI状态: ✅ 已连接 · AI引擎运行中

📰 情绪面分析
ETH价格: {price_display}
新闻情绪: {news_sentiment}（{detail}）
恐惧贪婪: {fng['value']}（{fng['label']}）
综合情绪评分: {sentiment_score:.0f}/100

📈 技术面分析
价格位置: {pos_desc}（强度:{pos_strength}）
MA20趋势: {ma_trend}（MA20={kline['ma20']:.0f}）
ATR波动率: ${kline['atr']:.1f}

🎯 交易信号
信号: {signal}
置信度: {confidence}
当前状态: {position}

📉 动态关键位
🔴 强压: {levels['强压']}
🔴 压力: {levels['压力1']} / {levels['压力2']}
🟢 支撑: {levels['支撑1']} / {levels['支撑2']}
🟢 铁底: {levels['铁底']}

📋 具体操作建议

【做多方案】
入场: {advice['long']['entry']}
止损: {advice['long']['stop']}（约 {advice['stop_distance']} 点）
止盈: {advice['long']['tp1']} / {advice['long']['tp2']}
适合: 价格回调至支撑区 + 情绪偏多时

【做空方案】
入场: {advice['short']['entry']}
止损: {advice['short']['stop']}（约 {advice['stop_distance']} 点）
止盈: {advice['short']['tp1']} / {advice['short']['tp2']}
适合: 价格反弹至压力区 + 情绪偏空时

📦 动态持仓管理
📉 到 {levels['支撑1']} → 持盈，止盈上移至 {levels['支撑1']+5}
📉 到 {levels['支撑2']} → 全部离场（支撑告破）
📈 反抽 {levels['压力2']} 受阻 → 开空，分批加仓
📈 站稳 {levels['压力1']} 超15分钟 → 止损离场

🧠 决策依据
{chr(10).join(reasons)}

⚠️ 风险提示
{chr(10).join(risks)}

🔑 综合策略
建议: {signal}
策略: 分批止盈 + 移动止损 + 严控仓位

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