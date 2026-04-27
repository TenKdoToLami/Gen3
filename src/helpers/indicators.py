"""
Technical indicator helpers for Gen3 Trading Bot.
"""
import math

def sma(prices: list, period: int):
    if len(prices) < period: return None
    return sum(prices[-period:]) / period

def ema(prices: list, period: int, prev_ema: float = None):
    if len(prices) < period: return None
    k = 2 / (period + 1)
    if prev_ema is not None:
        return (prices[-1] * k) + (prev_ema * (1 - k))
    current_ema = sum(prices[:period]) / period
    for i in range(period, len(prices)):
        current_ema = (prices[i] * k) + (current_ema * (1 - k))
    return current_ema

def rsi(prices: list, period: int = 14, state: dict = None):
    if len(prices) < period + 1: return None
    if state and "avg_gain" in state and "avg_loss" in state:
        delta = prices[-1] - prices[-2]
        gain = delta if delta > 0 else 0
        loss = -delta if delta < 0 else 0
        state["avg_gain"] = (state["avg_gain"] * (period - 1) + gain) / period
        state["avg_loss"] = (state["avg_loss"] * (period - 1) + loss) / period
        if state["avg_loss"] == 0: return 100
        rs = state["avg_gain"] / state["avg_loss"]
        return 100 - (100 / (1 + rs))
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas[:period]]
    losses = [-d if d < 0 else 0 for d in deltas[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period, len(deltas)):
        gain = deltas[i] if deltas[i] > 0 else 0
        loss = -deltas[i] if deltas[i] < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if state is not None:
        state["avg_gain"] = avg_gain
        state["avg_loss"] = avg_loss
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(prices: list, fast: int = 12, slow: int = 26, signal: int = 9, state: dict = None):
    if len(prices) < slow + signal: return None, None, None
    if state and "fast_ema" in state and "slow_ema" in state:
        state["fast_ema"] = ema(prices, fast, prev_ema=state["fast_ema"])
        state["slow_ema"] = ema(prices, slow, prev_ema=state["slow_ema"])
        macd_line = state["fast_ema"] - state["slow_ema"]
        if "signal_ema" in state and state["signal_ema"] is not None:
            k = 2 / (signal + 1)
            state["signal_ema"] = (macd_line * k) + (state["signal_ema"] * (1 - k))
            return macd_line, state["signal_ema"], macd_line - state["signal_ema"]
    macd_history = []
    f_ema = sum(prices[:fast]) / fast
    s_ema = sum(prices[:slow]) / slow
    for i in range(len(prices)):
        if i >= fast:
            k_f = 2 / (fast + 1)
            f_ema = (prices[i] * k_f) + (f_ema * (1 - k_f))
        if i >= slow:
            k_s = 2 / (slow + 1)
            s_ema = (prices[i] * k_s) + (s_ema * (1 - k_s))
        if i >= slow:
            macd_history.append(f_ema - s_ema)
    macd_line = macd_history[-1]
    signal_line = ema(macd_history, signal)
    if state is not None:
        state["fast_ema"] = f_ema
        state["slow_ema"] = s_ema
        state["signal_ema"] = signal_line
    return macd_line, signal_line, macd_line - signal_line

def realized_volatility(prices: list, window: int = 20):
    if len(prices) < window + 1: return None
    log_returns = [math.log(prices[i] / prices[i - 1]) for i in range(-window, 0)]
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    return math.sqrt(variance) * math.sqrt(252)

def linear_regression_slope(prices: list, period: int = 20):
    if len(prices) < period: return None
    y = prices[-period:]
    x = list(range(period))
    n = period
    sum_x, sum_y = sum(x), sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi**2 for xi in x)
    den = (n * sum_x2 - sum_x**2)
    return (n * sum_xy - sum_x * sum_y) / den if den != 0 else 0

def trix(prices: list, period: int = 15, state: dict = None):
    if len(prices) < period * 3: return None
    if state is None: state = {}
    ema1 = ema(prices, period, prev_ema=state.get("ema1"))
    if ema1 is None: return None
    state["ema1"] = ema1
    if "ema1_history" not in state: state["ema1_history"] = []
    state["ema1_history"].append(ema1)
    ema2 = ema(state["ema1_history"], period, prev_ema=state.get("ema2"))
    if ema2 is None: return None
    state["ema2"] = ema2
    if "ema2_history" not in state: state["ema2_history"] = []
    state["ema2_history"].append(ema2)
    ema3 = ema(state["ema2_history"], period, prev_ema=state.get("ema3"))
    if ema3 is None: return None
    res = (ema3 - state["prev_ema3"]) / state["prev_ema3"] * 100 if state.get("prev_ema3") else 0
    state["prev_ema3"] = ema3
    return res

def atr(highs: list, lows: list, closes: list, period: int = 14, prev_atr: float = None):
    if len(highs) < period + 1: return None
    tr = max(highs[-1]-lows[-1], abs(highs[-1]-closes[-2]), abs(lows[-1]-closes[-2]))
    if prev_atr is not None: return (prev_atr * (period - 1) + tr) / period
    tr_hist = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(1, len(highs))]
    return sum(tr_hist[-period:]) / period

def adx(highs: list, lows: list, closes: list, period: int = 14, state: dict = None):
    if len(highs) < period * 2: return None
    if state is None: state = {}
    up, down = highs[-1]-highs[-2], lows[-2]-lows[-1]
    tr = max(highs[-1]-lows[-1], abs(highs[-1]-closes[-2]), abs(lows[-1]-closes[-2]))
    dp, dm = (up if up > down and up > 0 else 0), (down if down > up and down > 0 else 0)
    if "smooth_tr" not in state:
        tr_h, p_h, m_h = [], [], []
        for i in range(1, len(highs)):
            tr_h.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])))
            u, d = highs[i]-highs[i-1], lows[i-1]-lows[i]
            p_h.append(u if u > d and u > 0 else 0)
            m_h.append(d if d > u and d > 0 else 0)
        state["smooth_tr"], state["smooth_plus"], state["smooth_minus"] = sum(tr_h[-period:])/period, sum(p_h[-period:])/period, sum(m_h[-period:])/period
    else:
        state["smooth_tr"] = (state["smooth_tr"]*(period-1)+tr)/period
        state["smooth_plus"] = (state["smooth_plus"]*(period-1)+dp)/period
        state["smooth_minus"] = (state["smooth_minus"]*(period-1)+dm)/period
    if state["smooth_tr"] == 0: return 0
    dip, dim = 100*state["smooth_plus"]/state["smooth_tr"], 100*state["smooth_minus"]/state["smooth_tr"]
    dx = 100*abs(dip-dim)/(dip+dim) if (dip+dim) != 0 else 0
    state["adx"] = (state["adx"]*(period-1)+dx)/period if state.get("adx") else dx
    return state["adx"]
