def generate_report():
    now = get_beijing_time()
    price = get_eth_price()
    price_display = f"${price:.2f}"
    
    # ===== 获取真实K线数据 =====
    kline_data = get_detailed_klines()  # 新函数，获取完整K线数据
    atr = kline_data['atr']
    recent_high = max(kline_data['highs'][-20:])
    recent_low = min(kline_data['lows'][-20:])
    
    # ===== 基于真实数据计算关键位 =====
    # 支撑：近期低点，如果价格在低点下方，则取当前价-1.5倍ATR
    if price > recent_low:
        support_1 = recent_low
        support_2 = recent_low - atr * 0.5
    else:
        support_1 = price - atr * 0.5
        support_2 = price - atr * 1.2
    
    # 压力：近期高点，如果价格在高点上方，则取当前价+1.5倍ATR
    if price < recent_high:
        resistance_1 = recent_high
        resistance_2 = recent_high + atr * 0.5
    else:
        resistance_1 = price + atr * 0.5
        resistance_2 = price + atr * 1.2
    
    # ===== 基于真实数据生成入场建议 =====
    # 做多入场：在支撑位附近（距离支撑位3点以内直接入场，否则等回调）
    if abs(price - support_1) <= 3:
        long_entry = f"{price:.0f}"
    elif price > support_1:
        long_entry = f"{support_1:.0f}-{support_1+3:.0f}"
    else:
        long_entry = f"{price:.0f}-{price+3:.0f}"
    
    long_stop = f"{float(long_entry.split('-')[0]) - atr * 1.5:.0f}"
    long_tp1 = f"{float(long_entry.split('-')[0]) + (float(long_entry.split('-')[0]) - float(long_stop)) * 2:.0f}"
    long_tp2 = f"{resistance_1:.0f}"
    
    # ===== 同样逻辑计算做空方案 =====
    if abs(price - resistance_1) <= 3:
        short_entry = f"{price:.0f}"
    elif price < resistance_1:
        short_entry = f"{resistance_1:.0f}-{resistance_1+3:.0f}"
    else:
        short_entry = f"{price:.0f}-{price+3:.0f}"
    
    short_stop = f"{float(short_entry.split('-')[0]) + atr * 1.5:.0f}"
    short_tp1 = f"{float(short_entry.split('-')[0]) - (float(short_stop) - float(short_entry.split('-')[0])) * 2:.0f}"
    short_tp2 = f"{support_1:.0f}"