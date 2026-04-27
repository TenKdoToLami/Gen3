from src.helpers.indicators import (
    sma, ema, rsi, macd, adx, atr, trix, linear_regression_slope, realized_volatility
)

class V3Strategy:
    """
    Precision Binary Strategy (3xSPY vs CASH).
    The production version of the Gen3 bot.
    Includes lock_days state machine to prevent whipsaw.
    """
    def __init__(self, genome):
        self.genome = genome
        self.reset()

    def reset(self):
        self.prices = []
        self.highs = []
        self.lows = []
        self.brain_states = {'panic': {}, 'bull': {}}
        self.last_holdings = None
        self.lock_counter = 0

    def _get_brain_score(self, brain_key, price_data):
        spy_price = self.prices[-1]
        brain = self.genome[brain_key]
        lb = brain['lookbacks']
        state = self.brain_states[brain_key]

        # 1. Indicators
        val_sma = sma(self.prices, int(round(lb['sma'])))
        val_ema = ema(self.prices, int(round(lb['ema'])), prev_ema=state.get('prev_ema'))
        state['prev_ema'] = val_ema
        val_rsi = rsi(self.prices, int(round(lb['rsi'])), state=state)
        
        m_f, m_s = int(round(lb['macd_f'])), int(round(lb['macd_s']))
        val_macd_tuple = macd(self.prices, m_f, m_s, state=state)
        val_macd = val_macd_tuple[0] if val_macd_tuple[0] is not None else 0.0
        
        val_adx = adx(self.highs, self.lows, self.prices, int(round(lb['adx'])), state=state)
        val_trix = trix(self.prices, int(round(lb['trix'])), state=state)
        val_slope = linear_regression_slope(self.prices, int(round(lb['slope'])))
        val_vol = realized_volatility(self.prices, int(round(lb['vol'])))
        val_atr = atr(self.highs, self.lows, self.prices, int(round(lb['atr'])), prev_atr=state.get('prev_atr'))
        state['prev_atr'] = val_atr

        # 2. Normalize
        macro_vix = float(price_data.get('vix', 15.0))
        macro_yc = float(price_data.get('yield_curve', 0.0))
        
        inputs = {
            'sma': ((spy_price - val_sma) / val_sma * 5) if val_sma else 0.0,
            'ema': ((spy_price - val_ema) / val_ema * 10) if val_ema else 0.0,
            'rsi': ((val_rsi or 50) - 50) / 50.0,
            'macd': val_macd / spy_price * 100,
            'adx': ((val_adx or 25) - 25) / 25.0,
            'trix': val_trix or 0.0,
            'slope': (val_slope or 0.0) / spy_price * 1000,
            'vol': (val_vol or 0.15) * 5,
            'atr': ((val_atr or 0.0) / spy_price) * 50,
            'vix': (macro_vix - 20) / 10.0,
            'yc': macro_yc
        }

        # 3. Weighted Sum
        score = 0
        for k, weight in brain['w'].items():
            if brain['a'].get(k, True):
                score += weight * inputs.get(k, 0.0)
        return score

    def on_data(self, price_data):
        """
        Processes one day of data and returns the target allocation.
        """
        self.prices.append(price_data['close'])
        self.highs.append(price_data['high'])
        self.lows.append(price_data['low'])

        if self.lock_counter > 0:
            self.lock_counter -= 1

        # Calculate both brain scores to keep internal indicator states updated
        score_panic = self._get_brain_score('panic', price_data)
        score_bull = self._get_brain_score('bull', price_data)

        # Base Decision
        if score_panic > self.genome['panic']['t']:
            new_holdings = {"CASH": 1.0}
        elif score_bull > self.genome['bull']['t']:
            new_holdings = {"3xSPY": 1.0}
        else:
            new_holdings = {"CASH": 1.0}

        # State Machine / Lock logic
        if new_holdings != self.last_holdings:
            # Panic override: If signal is CASH due to Panic, we exit immediately ignoring the lock
            is_panic = (new_holdings.get("CASH") == 1.0 and score_panic > self.genome['panic']['t'])
            
            if self.lock_counter == 0 or is_panic:
                self.last_holdings = new_holdings
                self.lock_counter = max(0, int(round(self.genome.get('lock_days', 0))))
                return new_holdings
            
        return self.last_holdings or {"CASH": 1.0}
