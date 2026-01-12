import pandas as pd
import numpy as np
from binance.client import Client
from datetime import datetime
import time
import ssl
import certifi
from urllib3 import PoolManager

https = PoolManager(
    ssl_context=ssl.create_default_context(cafile=certifi.where())
)


# ====== Binance PUBLIC client ======
client = Client()  # Bez klucza API, tylko publiczne dane

# ====== Parametry symulacji ======
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
initial_balance = 1000
risk_reward_ratio = 3

stop_loss_pct = 0.01
volume_drop_min_pct = 0.05
ema_alignment_min = 0.0

balances = {s: initial_balance for s in symbols}
trades_history = {s: [] for s in symbols}

# ====== Dane rynkowe ======
def get_data(symbol, limit=120):
    klines = client.get_klines(
        symbol=symbol,
        interval=Client.KLINE_INTERVAL_1MINUTE,
        limit=limit
    )
    df = pd.DataFrame(klines, columns=[
        'open_time','open','high','low','close','volume',
        'close_time','qav','trades','tbb','tbq','ignore'
    ])
    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)

    # EMA
    df['EMA9'] = df['close'].ewm(span=9).mean()
    df['EMA13'] = df['close'].ewm(span=13).mean()
    df['EMA21'] = df['close'].ewm(span=21).mean()
    df['EMA50'] = df['close'].ewm(span=50).mean()

    # VWAP
    df['VWAP'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    return df

# ====== Strategia ======
def check_buy_signal(df):
    r, p = df.iloc[-1], df.iloc[-2]
    return (
        r['close'] < r['VWAP'] and
        (p['volume'] - r['volume']) / max(p['volume'], 1) > volume_drop_min_pct and
        r['EMA9'] >= r['EMA13'] >= r['EMA21']
    )

# ====== LM Studio (Localhost1234) ======
LM_NAME = "Local LM Studio localhost1234"

def lm_studio(df, trades_history_symbol, model_name="default_model"):
    """
    Lokalny LM Studio podłączony do localhost:1234
    - model_name: nazwa wybranego modelu w LM Studio
    - fallback: rule-based jeśli brak połączenia
    """
    row = df.iloc[-1]
    prev = df.iloc[-2]

    buy_decision = False
    feedback = ""

    try:
        # Tutaj byłoby wywołanie prawdziwego LLM z LM Studio:
        # np. wysyłasz df + trades_history_symbol + model_name do serwera LM Studio
        # i otrzymujesz decyzję i feedback
        # Dla demonstracji używamy rule-based fallback

        if row['EMA9'] > row['EMA21'] and row['close'] > row['VWAP']:
            buy_decision = True

        # Analiza historii ostatnich 50 trade'ów
        last_trades = trades_history_symbol[-50:]
        if last_trades:
            wins = sum(1 for t in last_trades if t['outcome']=="WIN")
            losses = sum(1 for t in last_trades if t['outcome']=="LOSS")
            if losses > wins:
                feedback = f"[{LM_NAME}] Zbyt wiele strat! Zmniejsz SL lub poczekaj na większy spadek wolumenu."

        # Dodatkowe sugestie
        if row['volume'] < prev['volume']*0.5:
            feedback += f" [{LM_NAME}] Volume spadkowy bardzo niski – może koniec trendu spadkowego."

        # Dodaj informację o używanym modelu
        feedback += f" (Model użyty: {model_name})"

    except Exception as e:
        feedback = f"[{LM_NAME}] Błąd LM Studio: {e} (użyto fallback rule-based)"
        buy_decision = row['EMA9'] > row['EMA21']  # fallback

    return buy_decision, feedback

def calculate_levels(price):
    sl = price * (1 - stop_loss_pct)
    tp = price + (price - sl) * risk_reward_ratio
    return sl, tp

# ====== Główna pętla ======
print(f"▶ Binance paper trading + LM Studio ({LM_NAME})")

while True:
    try:
        for s in symbols:
            df = get_data(s)
            price = df['close'].iloc[-1]

            # Strategia + LM Studio
            strategy_signal = check_buy_signal(df)
            lm_signal, lm_feedback = lm_studio(df, trades_history[s], model_name="gpt-5-mini")

            if strategy_signal and lm_signal:
                sl, tp = calculate_levels(price)
                amount = balances[s] * 0.1

                trades_history[s].append({
                    "time": datetime.now(),
                    "symbol": s,
                    "entry": price,
                    "sl": sl,
                    "tp": tp,
                    "amount": amount,
                    "outcome": "OPEN",
                    "balance": balances[s]
                })

                print(f"{s} BUY @ {price:.2f} SL {sl:.2f} TP {tp:.2f} | {lm_feedback}")

            # Aktualizacja otwartych trade'ów
            for t in trades_history[s]:
                if t['outcome']=="OPEN":
                    if price >= t['tp']:
                        t['outcome'] = "WIN"
                        balances[s] += amount * stop_loss_pct * risk_reward_ratio
                    elif price <= t['sl']:
                        t['outcome'] = "LOSS"
                        balances[s] -= amount * stop_loss_pct

            closed = [t for t in trades_history[s] if t['outcome'] != "OPEN"]
            winrate = len([t for t in closed if t['outcome']=="WIN"]) / max(len(closed),1)

            print(f"{s} | Balance: {balances[s]:.2f}$ | WinRate: {winrate*100:.1f}%")

        time.sleep(60)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(10)
