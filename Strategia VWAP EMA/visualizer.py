import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import glob
import time
from datetime import datetime

# ====== Parametry ======
refresh_interval = 60  # odświeżanie wykresu w sekundach
csv_pattern = "trade_history_*.csv"

def load_trades():
    csv_files = glob.glob(csv_pattern)
    trades_data = {}
    for f in csv_files:
        symbol = f.split("_")[-1].replace(".csv", "")
        df = pd.read_csv(f, parse_dates=['timestamp'])
        trades_data[symbol] = df
    return trades_data

def plot_trades(symbol, df):
    if df.empty:
        print(f"Brak danych dla {symbol}")
        return

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        row_heights=[0.7, 0.3], vertical_spacing=0.05,
                        subplot_titles=(f"{symbol} - Świece i trade'y", "Saldo i WinRatio"))

    # Wykres świecowy
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['entry'],  # w symulacji używamy entry jako open/close dla prostoty
        high=df['take_profit'],
        low=df['stop_loss'],
        close=df['entry'],
        name='Candlestick'
    ), row=1, col=1)

    # Sygnały wejścia i wyjścia
    buy_signals = df[df['outcome'] == 'OPEN']
    win_signals = df[df['outcome'] == 'WIN']
    loss_signals = df[df['outcome'] == 'LOSS']

    fig.add_trace(go.Scatter(x=buy_signals['timestamp'], y=buy_signals['entry'], mode='markers',
                             marker=dict(color='blue', size=8, symbol='circle'), name='Buy'), row=1, col=1)
    fig.add_trace(go.Scatter(x=win_signals['timestamp'], y=win_signals['take_profit'], mode='markers',
                             marker=dict(color='green', size=10, symbol='triangle-up'), name='TP Hit'), row=1, col=1)
    fig.add_trace(go.Scatter(x=loss_signals['timestamp'], y=loss_signals['stop_loss'], mode='markers',
                             marker=dict(color='red', size=10, symbol='triangle-down'), name='SL Hit'), row=1, col=1)

    # Wykres salda
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['balance_after'], mode='lines+markers',
                             name='Saldo USD', line=dict(color='orange')), row=2, col=1)

    # WinRatio w czasie
    df['win_ratio'] = df['outcome'].eq('WIN').cumsum() / (df['outcome'].isin(['WIN','LOSS']).cumsum())
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['win_ratio'], mode='lines',
                             name='WinRatio', line=dict(color='green')), row=2, col=1, secondary_y=False)

    fig.update_layout(height=700, width=1000, title_text=f"Monitorowanie {symbol} - quasi-live")
    fig.show()

# ====== Główna pętla ======
print("Uruchomiono wizualizator trade'ów...")

while True:
    try:
        trades_data = load_trades()
        for symbol, df in trades_data.items():
            plot_trades(symbol, df)
        time.sleep(refresh_interval)
    except Exception as e:
        print(f"Błąd wizualizacji: {e}")
        time.sleep(10)
