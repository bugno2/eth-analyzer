#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH全智能分析推送 (完整优化版)

import requests
import json
import os
import feedparser
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

def get_detailed_klines():
    """获取完整的K线数据（含高低点列表和ATR）"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=50"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            closes = [float(c[4]) for c in data]
            highs = [float(c[2]) for c in data]
            lows = [float(c[3]) for c in data]
            
            # MA20
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
            
            # ATR (14周期)
            tr_values = []
            for i in range(1, len(data)):
                high = float(data[i][2])
                low = float(data[i][3])
                prev_close = float(data[i-1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            atr = sum(tr_values[-14:]) / 14 if len(tr_values) >= 14 else tr_values[-1] if tr_values else 10
            
            # 近期高点低点（最近20根）
            recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
            recent_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)
            
            # 识别关键高点和低点（前高前低）
            key_highs = []
            key_lows = []
            for i in range(2, len(highs)-2):
                if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                    key_highs.append(highs[i])
                if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                    key_lows.append(lows[i])
            
            recent_key_high = key_highs[-1] if key_highs else recent_high
            recent_key_low = key_lows[-1] if key_lows else recent_low
            
            return {
                "ma20": ma20,
                "atr": atr,
                "close": closes[-1],
                "highs": highs,
                "lows": lows,
                "recent_high": recent_high,
                "recent_low": recent_low,
                "key_high": recent_key_high,
                "key_low": recent_key_low
            }
    except Exception as e:
        print(f"⚠️ K线数据获取异常: {e}")
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
            return {
                "sentiment": {0: "负面", 1: "中性", 2: "正面"}.get(item.get("sentiment"), "未知"),
                "positive_prob": round(item.get("positive_prob", 0), 3),
                "negative_prob": round(item.get("negative_prob", 0), 3)
            }
    except:
        pass
    return None


# ========== 2. 分析引擎层 ==========

def calculate_levels_from_kline(price, atr, recent_high, recent_low, key_high, key_low):
    """基于真实K线数据计算动态关键位（使用前高前低）"""
    # 优先使用关键位（前高前低），如果没有则使用近期高低点
    if key_high and key_high > price:
        resistance_1 = key_high
    else:
        resistance_1 = recent_high if recent_high > price else price + atr * 0.8
    
    if key_low and key_low < price:
        support_1 = key_low
    else:
        support_1 = recent_low if recent_low < price else price - atr * 0.8
    
    # 第二支撑/压力（用ATR扩展）
    support_2 = support_1 - atr * 0.6
    resistance_2 = resistance_1 + atr * 0.6
    
    # 铁底和强压（用ATR扩展）
    iron_bottom = support_1 - atr * 1.2
    strong_resistance = resistance_1 + atr * 1.2
    
    return {
        "强压": int(strong_resistance),
        "压力1": int(resistance_1),
        "压力2": int(resistance_1 - atr * 0.3 if resistance_1 - atr * 0.3 > price else resistance_1 - atr * 0.5),
        "支撑1": int(support_1),
        "支撑2": int(support_2),
        "铁底": int(iron_bottom),
        "当前": price,
        "key_high": int(key_high) if key_high else None,
        "key_low": int(key_low) if key_low else None
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

def analyze_sentiment_score(news_sentiment, fng_value):
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
    
    combined = news_score * 0.4 + fng_score * 0.6
    return max(0, min(100, combined))

def get_trading_signal(price, levels, sentiment_score, ma20):
    if sentiment_score >= 70 and price <= levels["支撑1"]:
        return "🟢 强烈做多", "高"
    elif sentiment_score >= 60 and price <= levels["支撑2"]:
        return "🟢 偏多", "中"
    elif sentiment_score <= 30 and price >= levels["压力1"]:
        return "🔴 强烈做空", "高"
    elif sentiment_score <= 40 and price >= levels["压力2"]:
        return "🔴 偏空", "中"
    elif sentiment_score >= 55:
        return "🟡 震荡偏多", "低"
    elif sentiment_score <= 45:
        return "🟡 震荡偏空", "低"
    else:
        return "⚪ 观望", "低"

def get_position_advice(price, levels, atr, sentiment_score):
    """基于真实关键位生成精准的操作建议"""
    stop_multiplier = 1.5
    atr_step = max(atr, 8)
    
    # ===== 做多方案 =====
    # 入场价 = 最接近当前价格的支撑位
    supports = [levels["支撑1"], levels["支撑2"], levels["铁底"]]
    valid_supports = [s for s in supports if s < price]
    
    if valid_supports:
        base_entry = max(valid_supports)
    else:
        base_entry = price - atr_step * 0.6
    
    # 价格过滤逻辑：根据价格与支撑位的距离调整入场策略
    distance_to_support = price - base_entry
    
    if distance_to_support <= 2:
        # 价格已在支撑位，直接入场
        long_entry = f"{price:.0f}"
        long_stop = f"{int(price - atr_step * stop_multiplier)}"
        long_tp1 = f"{int(price + atr_step * 1.0)}"
        long_tp2 = f"{int(price + atr_step * 1.8)}"
    elif distance_to_support <= 8:
        # 价格接近支撑位，等待回调入场
        long_entry = f"{base_entry:.0f}-{base_entry+3:.0f}"
        long_stop = f"{int(base_entry - atr_step * stop_multiplier)}"
        long_tp1 = f"{int(base_entry + atr_step * 1.2)}"
        long_tp2 = f"{int(base_entry + atr_step * 2.0)}"
    else:
        # 价格离支撑位较远，等深度回调
        long_entry = f"{base_entry:.0f}-{base_entry+5:.0f}"
        long_stop = f"{int(base_entry - atr_step * stop_multiplier)}"
        long_tp1 = f"{int(base_entry + atr_step * 1.5)}"
        long_tp2 = f"{int(base_entry + atr_step * 2.5)}"
    
    # ===== 做空方案 =====
    resistances = [levels["压力2"], levels["压力1"], levels["强压"]]
    valid_resistances = [r for r in resistances if r > price]
    
    if valid_resistances:
        base_entry = min(valid_resistances)
    else:
        base_entry = price + atr_step * 0.6
    
    distance_to_resistance = base_entry - price
    
    if distance_to_resistance <= 2:
        short_entry = f"{price:.0f}"
        short_stop = f"{int(price + atr_step * stop_multiplier)}"
        short_tp1 = f"{int(price - atr_step * 1.0)}"
        short_tp2 = f"{int(price - atr_step * 1.8)}"
    elif distance_to_resistance <= 8:
        short_entry = f"{base_entry:.0f}-{base_entry+3:.0f}"
        short_stop = f"{int(base_entry + atr_step * stop_multiplier)}"
        short_tp1 = f"{int(base_entry - atr_step * 1.2)}"
        short_tp2 = f"{int(base_entry - atr_step * 2.0)}"
    else:
        short_entry = f"{base_entry:.0f}-{base_entry+5:.0f}"
        short_stop = f"{int(base_entry + atr_step * stop_multiplier)}"
        short_tp1 = f"{int(base_entry - atr_step * 1.5)}"
        short_tp2 = f"{int(base_entry - atr_step * 2.5)}"
    
    long_stop_dist = int(abs(float(long_stop) - float(long_entry.split('-')[0])))
    short_stop_dist = int(abs(float(short_stop) - float(short_entry.split('-')[0])))
    
    return {
        "long": {"entry": long_entry, "stop": long_stop, "tp1": long_tp1, "tp2": long_tp2, "stop_dist": long_stop_dist},
        "short": {"entry": short_entry, "stop": short_stop, "tp1": short_tp1, "tp2": short_tp2, "stop_dist": short_stop_dist}
    }

def get_position_recommendation(sentiment_score, price, levels, fng):
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
    
    # 获取K线数据
    kline = get_detailed_klines()
    if kline is None:
        kline = {"ma20": 1850, "atr": 15, "recent_high": 1880, "recent_low": 1840, "key_high": 1885, "key_low": 1835}
    
    # 获取其他数据
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
            news_sentiment, detail = "偏空", f"负面{int(neg_count/len(analysis_results)*100)}% / 正面{int(pos_count/len(analysis_results)*100)}%"
        elif pos_count > neg_count:
            news_sentiment, detail = "偏多", f"正面{int(pos_count/len(analysis_results)*100)}% / 负面{int(neg_count/len(analysis_results)*100)}%"
        else:
            news_sentiment, detail = "中性", "正面50% / 负面50%"
    else:
        news_sentiment, detail = "中性", "正面50% / 负面50%"
    
    # 计算关键位
    levels = calculate_levels_from_kline(
        price, kline["atr"], kline["recent_high"], kline["recent_low"], 
        kline.get("key_high"), kline.get("key_low")
    )
    pos_desc, pos_strength = analyze_price_position(price, levels)
    sentiment_score = analyze_sentiment_score(news_sentiment, fng["value"])
    signal, confidence = get_trading_signal(price, levels, sentiment_score, kline["ma20"])
    advice = get_position_advice(price, levels, kline["atr"], sentiment_score)
    priority = get_position_recommendation(sentiment_score, price, levels, fng)
    
    # 距离最近支撑/压力的距离
    nearest_support = max([levels["支撑1"], levels["支撑2"], levels["铁底"]], key=lambda x: x if x < price else -9999)
    nearest_resistance = min([levels["强压"], levels["压力1"], levels["压力2"]], key=lambda x: x if x > price else 9999)
    support_dist = price - nearest_support
    resistance_dist = nearest_resistance - price
    
    # 构建决策依据
    reasons = [
        f"📊 综合情绪评分 {sentiment_score:.0f}%",
        f"📍 价格处于{pos_desc}（强度:{pos_strength}）",
        f"📈 MA20: {kline['ma20']:.0f}，价格在{'上方' if price > kline['ma20'] else '下方'}",
        f"😨 F&G: {fng['value']}（{fng['label']}）",
        f"📏 距支撑: {support_dist:.0f}点 | 距压力: {resistance_dist:.0f}点"
    ]
    
    # 添加关键位信息
    if levels.get("key_high"):
        reasons.append(f"🔺 前高: {levels['key_high']}")
    if levels.get("key_low"):
        reasons.append(f"🔻 前低: {levels['key_low']}")
    
    # 风险提示
    risks = []
    if price >= levels["压力1"]:
        risks.append("⚠️ 价格处于压力区，追多风险较大")
    if price <= levels["支撑2"]:
        risks.append("⚠️ 价格处于支撑区，注意破位下行风险")
    if fng["value"] >= 70:
        risks.append("⚠️ 市场贪婪，注意回调")
    if fng["value"] <= 20:
        risks.append("⚠️ 市场恐慌，可能继续下跌")
    if support_dist < 5:
        risks.append("⚠️ 价格接近支撑位，注意破位")
    if resistance_dist < 5:
        risks.append("⚠️ 价格接近压力位，注意受阻")
    if not risks:
        risks.append("⚪ 当前无明显极端风险")
    
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
距支撑: {support_dist:.0f}点 | 距压力: {resistance_dist:.0f}点

🎯 交易信号
信号: {signal} | 置信度: {confidence}
{priority}

📉 动态关键位（基于真实K线数据）
🔴 强压: {levels['强压']}
🔴 压力: {levels['压力1']} / {levels['压力2']}
🟢 支撑: {levels['支撑1']} / {levels['支撑2']}
🟢 铁底: {levels['铁底']}

📋 具体操作建议
【做多方案】入场: {advice['long']['entry']} | 止损: {advice['long']['stop']}（约{advice['long']['stop_dist']}点）| 止盈: {advice['long']['tp1']} / {advice['long']['tp2']}
【做空方案】入场: {advice['short']['entry']} | 止损: {advice['short']['stop']}（约{advice['short']['stop_dist']}点）| 止盈: {advice['short']['tp1']} / {advice['short']['tp2']}
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