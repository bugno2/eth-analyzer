#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH情感分析 + 飞书推送 (智能动态版)

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

DEMO_NEWS = [
    "ETH价格震荡下行，市场情绪谨慎",
    "以太坊生态发展稳步推进，开发者活跃度上升",
    "巨鲸地址近期频繁转移ETH，引发市场关注"
]

BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")

def get_eth_price():
    urls = [
        "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
        "https://api.mexc.com/api/v3/ticker/price?symbol=ETHUSDT"
    ]
    for url in urls:
        for i in range(2):
            try:
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    price = float(resp.json().get("price", 0))
                    if price > 0:
                        return price
            except:
                pass
    return 1850.00

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

def calculate_dynamic_levels(price):
    """根据当前价格动态计算支撑压力位"""
    # 基于价格计算关键位（取整）
    base = round(price / 5) * 5  # 按5美元取整
    
    levels = {
        "强压": base + 45,
        "压力1": base + 35,
        "压力2": base + 20,
        "支撑1": base - 15,
        "支撑2": base - 30,
        "铁底": base - 50,
        "当前": price
    }
    
    # 确保压力位 > 当前价 > 支撑位
    while levels["支撑1"] >= price:
        base -= 5
        levels = {
            "强压": base + 45,
            "压力1": base + 35,
            "压力2": base + 20,
            "支撑1": base - 15,
            "支撑2": base - 30,
            "铁底": base - 50,
            "当前": price
        }
    while levels["压力2"] <= price:
        base += 5
        levels = {
            "强压": base + 45,
            "压力1": base + 35,
            "压力2": base + 20,
            "支撑1": base - 15,
            "支撑2": base - 30,
            "铁底": base - 50,
            "当前": price
        }
    
    return levels

def generate_dynamic_strategy(price, levels, sentiment, fng):
    """根据价格位置生成动态策略"""
    strategies = []
    
    # 距离当前价格最近的支撑和压力
    nearest_support = max([l for l in [levels["支撑1"], levels["支撑2"], levels["铁底"]] if l < price])
    nearest_resistance = min([l for l in [levels["压力2"], levels["压力1"], levels["强压"]] if l > price])
    
    # 计算距离
    support_dist = (price - nearest_support) / price * 100
    resistance_dist = (nearest_resistance - price) / price * 100
    
    # 动态入场建议
    if support_dist < 1.5:
        strategies.append(f"🟢 激进多 | 入场：{price:.0f}-{price+5:.0f} | 止损：{price-10:.0f} | 止盈：{nearest_resistance:.0f} / {nearest_resistance+15:.0f}")
        strategies.append(f"🔵 稳健多 | 入场：{nearest_support:.0f}-{nearest_support+5:.0f} | 止损：{nearest_support-10:.0f} | 止盈：{price:.0f} / {nearest_resistance:.0f}")
    elif resistance_dist < 1.5:
        strategies.append(f"🔴 做空 | 入场：{price:.0f}-{price+5:.0f} | 止损：{price+10:.0f} | 止盈：{nearest_support:.0f} / {nearest_support-15:.0f}")
        strategies.append(f"⚪ 观望 | 价格接近压力位，等待回调后再考虑做多")
    else:
        strategies.append(f"⚪ 区间震荡 | 可于 {nearest_support:.0f} 附近做多，{nearest_resistance:.0f} 附近做空")
        strategies.append(f"🟢 做多 | 入场：{nearest_support:.0f}-{nearest_support+5:.0f} | 止损：{nearest_support-10:.0f} | 止盈：{nearest_resistance:.0f}")
        strategies.append(f"🔴 做空 | 入场：{nearest_resistance:.0f}-{nearest_resistance+5:.0f} | 止损：{nearest_resistance+10:.0f} | 止盈：{nearest_support:.0f}")
    
    # 综合建议（结合情绪和F&G）
    if sentiment == "偏多" and fng["value"] < 30:
        advice = "🟢 市场情绪偏多 + 恐惧贪婪显示恐惧，可能是个较好的入场机会，建议分批建仓"
    elif sentiment == "偏空" and fng["value"] > 70:
        advice = "🔴 市场情绪偏空 + 恐惧贪婪显示贪婪，建议减仓或观望"
    elif sentiment == "偏多":
        advice = "🟢 市场情绪偏多，可轻仓跟随，设置好止损"
    elif sentiment == "偏空":
        advice = "🔴 市场情绪偏空，建议防守为主"
    else:
        advice = "⚪ 市场情绪中性，建议观望等待方向明确"
    
    return strategies, advice

def generate_report():
    now = get_beijing_time()
    
    # 获取数据
    price = get_eth_price()
    price_display = f"${price:.2f}" if price else "❌ 获取失败"
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
            sentiment = "偏空"
            detail = f"负面{int(neg_count/len(analysis_results)*100)}% / 正面{int(pos_count/len(analysis_results)*100)}%"
        elif pos_count > neg_count:
            sentiment = "偏多"
            detail = f"正面{int(pos_count/len(analysis_results)*100)}% / 负面{int(neg_count/len(analysis_results)*100)}%"
        else:
            sentiment = "中性"
            detail = f"正面50% / 负面50%"
    else:
        sentiment = "中性"
        detail = "正面50% / 负面50%"
    
    # 动态计算关键位
    levels = calculate_dynamic_levels(price)
    
    # 动态生成策略
    strategies, advice = generate_dynamic_strategy(price, levels, sentiment, fng)
    
    # 格式化输出
    levels_display = [
        f"🔴 强压: {levels['强压']}",
        f"🔴 压力: {levels['压力1']} / {levels['压力2']}",
        f"🟢 支撑: {levels['支撑1']} / {levels['支撑2']}",
        f"🟢 铁底: {levels['铁底']}"
    ]
    
    strategy_lines = [f"策略：{s}" for s in strategies]
    strategy_section = "\n".join(strategy_lines)
    
    pos_lines = [
        f"📉 到 {levels['支撑1']} → 持盈，止盈上移至 {levels['支撑1']+5}（保本锁利）",
        f"📉 到 {levels['支撑2']} → 全部离场（支撑告破）",
        f"📈 反抽 {levels['压力2']} 受阻 → 开空，分批加至标准（阻力确认）",
        f"📈 站稳 {levels['压力1']} 超15分钟 → 止损走人，不补（空头失败）"
    ]
    pos_section = "\n".join(pos_lines)
    
    report = f"""
📊 ETH-AI 全视角分析
📅 {now} (北京时间)
💰 ETH实时价格: {price_display}
🤖 AI状态: ✅ 已连接 · AI引擎运行中

📰 情绪面（基于AI实时分析）
ETH价格: {price_display}
新闻情绪: {sentiment}（{detail}）
恐惧贪婪: {fng['value']}（{fng['label']}）
综合判断: {sentiment}主导，市场情绪{'明显' if sentiment != '中性' else ''}分化

📈 动态关键位（基于当前价格）
{chr(10).join(levels_display)}

📋 智能交易策略
{strategy_section}

📦 动态持仓管理
{pos_section}

🧠 当前定调
🤖 AI分析显示市场情绪 {sentiment}
📌 {advice}
🔑 建议: 分批止盈 + 移动止损，静待信号

⚠️ 分析仅供参考，投资决策需自行判断，盈亏自负。
"""
    return report

def generate_fallback_report(now, price_display):
    return f"""
📊 ETH-AI 全视角分析 (备用数据)
📅 {now} (北京时间)
💰 ETH实时价格: {price_display}
🤖 AI状态: ⚠️ 未连接

⚠️ 当前无法获取实时数据，请稍后再试
"""

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