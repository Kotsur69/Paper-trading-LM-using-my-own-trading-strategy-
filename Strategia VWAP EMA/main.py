import pandas as pd
from tradingview_ta import TA_Handler, Interval
from datetime import datetime
import time
import os

# ====== Parametry symulacji ======
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]  # dowolna liczba symboli
initial_balance = 1000
risk_reward_ratio = 3

# Parametry strategii (będą modyfikowane przez LM)
stop_loss_pct = 0.01
volume_drop_min_pct = 0.05
ema_alignment_min = 0.0

# ====== Utworzenie handlerów dla wszystkich symboli ======
handlers = {s: TA_Handler(symbol=s, screener="crypto", exchange="BINANCE", interval=Interval.INTERVAL_1_MINUTE) for s in symbols}
balances = {s: initial_balance for s in symbols}
trades_history = {s: [] for s in symbols}

# ====== Funkcje strategii ======
def check_buy_signal(df):
    row = df.iloc[-1]
    prev_row = df.iloc[-2]
    price_below_vwap = row['close'] < row['VWAP']
    volume_decreasing = (prev_row['volume'] - row['volume']) / prev_row['volume'] >= volume_drop_min_pct
    emas_nakreslaja = (row['EMA9'] - row['EMA13'] >= ema_alignment_min) and (row['EMA13'] - row['EMA21'] >= ema_alignment_min)
    return price_below_vwap and volume_decreasing and emas_nakreslaja

def lm_predict(df):
    """ Miejsce na lokalny LM Studio """
    from random import choice
    return choice([True, False])

def calculate_levels(entry_price, stop_loss_pct, rr):
    stop_loss = entry_price * (1 - stop_loss_pct)
    take_profit = entry_price + (entry_price - stop_loss) * rr
    return stop_loss, take_profit

def lm_strategy_feedback(trade_history_df):
    """ Feedback LM na podstawie ostatnich 50 trade'ów """
    if trade_history_df.empty:
        return {}
    last_trades = trade_history_df.tail(50)
    wins = last_trades[last_trades['outcome'] == "WIN"].shape[0]
    losses = last_trades[last_trades['outcome'] == "LOSS"].shape[0]
    suggestion = {}
    comment = ""
    if losses > wins:
        suggestion = {
            "stop_loss_pct": stop_loss_pct * 0.8,
            "volume_drop_min_pct": volume_drop_min_pct * 1.2,
            "ema_alignment_min": ema_alignment_min + 0.001,
        }
        comment = ("Zbyt wiele strat. LM sugeruje ostrożniejsze wejścia. "
                   "Rozważ użycie dodatkowych wskaźników: RSI, MACD, Bollinger Bands, OBV dla poprawy WinRatio.")
    return {**suggestion, "comment": comment}

def get_data(symbol):
    analysis = handlers[symbol].get_analysis()
    df = pd.DataFrame([analysis.indicators])
    df['close'] = analysis.indicators['close']
    df['volume'] = analysis.indicators['volume']
    df['EMA9'] = analysis.indicators['EMA9']
    df['EMA13'] = analysis.indicators['EMA13']
    df['EMA21'] = analysis.indicators['EMA21']
    df['EMA50'] = analysis.indicators['EMA50']
    df['VWAP'] = analysis.indicators['VWAP']
    return df

def save_trades_csv(trades_list, symbol):
    df = pd.DataFrame(trades_list)
    filename = f"trade_history_{symbol}.csv"
    df.to_csv(filename, index=False)

# ====== Główna pętla symulacji ======
print(f"Start symulacji 1-min dla par: {', '.join(symbols)}")

while True:
    try:
        for s in symbols:
            df = get_data(s)
            if df.shape[0] >= 2:
                # Sprawdzenie sygnału wejścia
                if check_buy_signal(df) and lm_predict(df):
                    entry_price = df['close'].iloc[-1]
                    stop_loss, take_profit = calculate_levels(entry_price, stop_loss_pct, risk_reward_ratio)
                    trade_amount = balances[s] * 0.1
                    trade = {
                        "timestamp": datetime.now(),
                        "symbol": s,
                        "entry": entry_price,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "amount": trade_amount,
                        "outcome": "OPEN",
                        "profit_loss": 0,
                        "balance_after": balances[s]
                    }
                    trades_history[s].append(trade)
                    print(f"{datetime.now()} | {s}: Sygnał KUPNA! Entry: {entry_price:.2f} | SL: {stop_loss:.2f} | TP: {take_profit:.2f}")

                # Aktualizacja otwartych trade'ów (hipotetyczne)
                for t in trades_history[s]:
                    if t['outcome'] == "OPEN":
                        current_price = df['close'].iloc[-1]
                        if current_price >= t['take_profit']:
                            t['outcome'] = "WIN"
                            t['profit_loss'] = t['amount'] * risk_reward_ratio * stop_loss_pct
                            balances[s] += t['profit_loss']
                            t['balance_after'] = balances[s]
                        elif current_price <= t['stop_loss']:
                            t['outcome'] = "LOSS"
                            t['profit_loss'] = -t['amount'] * stop_loss_pct
                            balances[s] += t['profit_loss']
                            t['balance_after'] = balances[s]

                # Status i WinRatio
                closed_trades = [tr for tr in trades_history[s] if tr['outcome'] in ["WIN","LOSS"]]
                if closed_trades:
                    win_trades = [tr for tr in closed_trades if tr['outcome']=="WIN"]
                    win_ratio = len(win_trades)/len(closed_trades)
                else:
                    win_ratio = 0
                print(f"{s} | Saldo: ${balances[s]:.2f} | Trade'ów: {len(closed_trades)} | WinRatio: {win_ratio*100:.2f}%")

                # Feedback LM co 50 trade'ów
                trades_df = pd.DataFrame(trades_history[s])
                feedback = lm_strategy_feedback(trades_df)
                if feedback:
                    stop_loss_pct = feedback.get("stop_loss_pct", stop_loss_pct)
                    volume_drop_min_pct = feedback.get("volume_drop_min_pct", volume_drop_min_pct)
                    ema_alignment_min = feedback.get("ema_alignment_min", ema_alignment_min)
                    print(f"LM Feedback ({s}): {feedback.get('comment')} | Nowe parametry -> stop_loss: {stop_loss_pct:.4f}, volume_drop_min_pct: {volume_drop_min_pct:.4f}, ema_alignment_min: {ema_alignment_min:.4f}")

                # Zapis historii do CSV
                save_trades_csv(trades_history[s], s)

        time.sleep(60)  # czekamy minutę przed kolejną świecą

    except Exception as e:
        print(f"Błąd: {e}")
        time.sleep(10)
