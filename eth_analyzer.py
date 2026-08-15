def get_hourly_levels(price):
    """获取4小时级关键位（日内交易用）"""
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=6"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            # 取最近4小时（排除当前未完成K线）
            recent_data = data[-6:-1] if len(data) >= 6 else data[:-1]
            highs = [float(c[2]) for c in recent_data]
            lows = [float(c[3]) for c in recent_data]
            
            # 4小时高点和低点
            high_4h = max(highs) if highs else price + 10
            low_4h = min(lows) if lows else price - 10
            
            # 计算ATR（1小时级别）
            tr_values = []
            for i in range(1, len(data)):
                high = float(data[i][2])
                low = float(data[i][3])
                prev_close = float(data[i-1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            atr = sum(tr_values[-6:]) / 6 if len(tr_values) >= 6 else 10
            
            # 动态入场位：基于当前价格和4小时区间
            if price < (high_4h + low_4h) / 2:
                # 价格在中轴下方，偏多思路
                long_entry = low_4h
                long_stop = low_4h - atr
                long_tp1 = price + atr * 0.8
                long_tp2 = high_4h
                short_entry = high_4h
                short_stop = high_4h + atr
                short_tp1 = price - atr * 0.8
                short_tp2 = low_4h
            else:
                # 价格在中轴上方，偏空思路
                long_entry = low_4h
                long_stop = low_4h - atr
                long_tp1 = price + atr * 0.8
                long_tp2 = high_4h
                short_entry = high_4h
                short_stop = high_4h + atr
                short_tp1 = price - atr * 0.8
                short_tp2 = low_4h
            
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
    except:
        return None
    return None

def generate_report():
    now = get_beijing_time()
    price = get_eth_price()
    price_display = f"${price:.2f}"
    
    # 1. 日线级关键位（稳定，看方向）
    daily_levels = get_daily_levels()
    if daily_levels is None:
        daily_levels = {"压力": price + 20, "支撑": price - 20}
    
    # 2. 小时级关键位（动态，定入场）
    hourly_levels = get_hourly_levels(price)
    if hourly_levels is None:
        hourly_levels = {
            "压力": price + 8, "支撑": price - 8,
            "long_entry": price - 5, "long_stop": price - 12,
            "long_tp1": price + 5, "long_tp2": price + 12,
            "short_entry": price + 5, "short_stop": price + 12,
            "short_tp1": price - 5, "short_tp2": price - 12
        }
    
    # 3. 计算当前价格在日内区间的百分比位置
    range_high = daily_levels.get("昨日高", daily_levels["压力"])
    range_low = daily_levels.get("昨日低", daily_levels["支撑"])
    if range_high > range_low:
        position_pct = (price - range_low) / (range_high - range_low) * 100
        position_pct_text = f"（日内位置：{position_pct:.0f}%）"
    else:
        position_pct_text = ""
    
    # 4. 生成报告
    report = f"""
📊 ETH 智能分析简报
⏰ {now}
💰 价格: {price_display} {position_pct_text}

📰 情绪: {sentiment_text} | 恐惧贪婪: {fng['value']}（{fng['label']}）

📈 今日大方向（日线级）
🔴 日线压力: {daily_levels['压力']}
🟢 日线支撑: {daily_levels['支撑']}

📊 日内交易区（4小时级，可触及）
🔴 短期压力: {hourly_levels['压力']}
🟢 短期支撑: {hourly_levels['支撑']}
📍 当前: {price_display} → {position_text}

📋 操作参考
【做多】入场 {hourly_levels['long_entry']} | 止损 {hourly_levels['long_stop']} | 止盈 {hourly_levels['long_tp1']}/{hourly_levels['long_tp2']}
【做空】入场 {hourly_levels['short_entry']} | 止损 {hourly_levels['short_stop']} | 止盈 {hourly_levels['short_tp1']}/{hourly_levels['short_tp2']}
📌 策略: 分批止盈 + 移动止损
⚠️ 仅供参考，风险自担
"""
    return report