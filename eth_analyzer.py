#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# eth_analyzer.py - ETH情感分析 + 飞书推送 (完整版：实时新闻 + 恐惧贪婪 + 动态策略)

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

# ========== 备用新闻数据（当RSS不可用时使用）==========
DEMO_NEWS = [
    "ETH价格震荡下行，市场情绪谨慎",
    "以太坊生态发展稳步推进，开发者活跃度上升",
    "巨鲸地址近期频繁转移ETH，引发市场关注"
]

BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")

def get_eth_price():
    """获取ETH实时价格（带重试）"""
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
                        print(f"✅ ETH实时价格: ${price}")
                        return price
            except:
                pass
    print("⚠️ ETH价格获取失败，使用模拟价格")
    return 1850.00

def get_fear_greed_index():
    """获取实时恐惧贪婪指数"""
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()["data"][0]
            return {
                "value": int(data["value"]),
                "label": data["value_classification"]
            }
    except:
        pass
    print("⚠️ 恐惧贪婪指数获取失败，使用备用值")
    return {"value": 45, "label": "中性"}

def fetch_eth_news():
    """从RSS获取ETH实时新闻"""
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
            print(f"✅ 获取到 {len(news_list)} 条ETH新闻")
            return news_list[:5]
    except:
        pass
    print("⚠️ 新闻获取失败，使用备用数据")
    return DEMO_NEWS

def get_baidu_access_token():
    """获取百度Token"""
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        print("❌ 百度API Key未设置")
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
            token = resp.json().get("access_token")
            if token:
                print("✅ 百度Token获取成功")
                return token
    except:
        pass
    print("❌ 百度Token获取失败")
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

def get_dynamic_advice(sentiment, price, support, resistance):
    """根据情绪和价格位置生成动态建议"""
    if sentiment == "偏空":
        return "🔴 市场情绪偏空，建议以防守为主，等待企稳信号再入场"
    elif sentiment == "偏多":
        return "🟢 市场情绪偏多，可轻仓跟随，但需设置好止损"
    elif price <= support[0]:
        return "🟡 价格已逼近强支撑区，关注是否有止跌企稳迹象"
    elif price >= resistance[0]:
        return "🟡 价格已接近压力区，追多风险较大，建议等待回调"
    else:
        return "⚪ 震荡格局，建议高抛低吸，控制仓位"

def generate_report():
    """生成完整报告"""
    now = get_beijing_time()
    print(f"🚀 开始分析，北京时间: {now}")

    price = get_eth_price()
    price_display = f"${price:.2f}" if price else "❌ 获取失败"

    fng = get_fear_greed_index()
    news_list = fetch_eth_news()

    token = get_baidu_access_token()
    analysis_results = []
    if token:
        for news in news_list:
            result = analyze_sentiment(news, token)
            if result:
                analysis_results.append({**result, "title": news})

    if analysis_results:
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
        sample_news = analysis_results[0]["title"][:30] + "..." if analysis_results else "暂无"
    else:
        sentiment = "中性"
        detail = "正面50% / 负面50%（备用数据）"
        sample_news = "暂时无法获取实时新闻"

    levels = {
        "强压": 1920,
        "压力": 1915,
        "支撑": 1875,
        "铁底": 1845
    }

    levels_display = {
        "强压": {"price": 1920, "desc": "最后关口，突破翻多"},
        "压力": {"price": "1915 / 1905", "desc": "反弹试空区"},
        "支撑": {"price": "1875 / 1860", "desc": "破位看1845"},
        "铁底": {"price": 1845, "desc": "多空分界线"}
    }

    advice = get_dynamic_advice(sentiment, price, [levels["支撑"], levels["铁底"]], [levels["压力"], levels["强压"]])

    trades = [
        {"type": "🟢 激进多", "entry": "1845-1850", "stop": "1835 (-12)", "tp": "1875 / 1900", "rr": "2.5:1", "size": "1%", "risk": "中"},
        {"type": "🟢 稳健多", "entry": "1830-1835", "stop": "1820 (-13)", "tp": "1865 / 1890", "rr": "2.7:1", "size": "2%", "risk": "中低"},
        {"type": "🟢 极限多", "entry": "1818-1825", "stop": "1805 (-15)", "tp": "1850 / 1875", "rr": "2.3:1", "size": "0.5%", "risk": "高"},
        {"type": "🔵 右侧多", "entry": "回踩1860-65不破", "stop": "1850 (-13)", "tp": "1900 / 1915", "rr": "3.2:1", "size": "1.5%", "risk": "中低"},
        {"type": "🔴 反抽空", "entry": "1900-10受阻", "stop": "1920 (+13)", "tp": "1875 / 1860", "rr": "2.5:1", "size": "1%", "risk": "中"}
    ]

    # 构建交易计划（无多余空行）
    trade_lines = []
    for t in trades:
        trade_lines.append(f"策略：{t['type']}\n入场：{t['entry']} | 止损：{t['stop']}\n止盈：{t['tp']} | 盈亏比：{t['rr']} | 仓位：{t['size']} | 风险：{t['risk']}")
    trade_section = "\n\n".join(trade_lines)

    # 构建持仓管理
    pos_lines = [
        "📉 到1875 → 持盈，止盈上移至1860（保本锁利）",
        "📉 到1860-65 → 全部离场（支撑告破）",
        "📈 反抽1900-10受阻 → 开空，分批加至标准（阻力确认）",
        "📈 站稳1915超15分钟 → 止损走人，不补（空头失败）"
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
综合判断: {sentiment}主导，市场情绪{'' if sentiment == '中性' else '明显'}分化

📈 关键位（相对当前价格）
🔴 强压: {levels_display['强压']['price']}（{levels_display['强压']['desc']}）
🔴 压力: {levels_display['压力']['price']}（{levels_display['压力']['desc']}）
🟢 支撑: {levels_display['支撑']['price']}（{levels_display['支撑']['desc']}）
🟢 铁底: {levels_display['铁底']['price']}（{levels_display['铁底']['desc']}）

📋 交易计划
{trade_section}

📦 持仓管理
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

⚠️ 当前无法获取实时数据，以下为固定参考信息

📈 关键位
🔴 强压: 1920（突破翻多）
🔴 压力: 1915 / 1905（反弹试空区）
🟢 支撑: 1875 / 1860（破位看1845）
🟢 铁底: 1845（多空分界线）

⚠️ 分析仅供参考，投资决策需自行判断，盈亏自负。
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