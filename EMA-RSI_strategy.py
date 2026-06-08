import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


INDEXES = {
    'USA':       '^GSPC',
    'INDIA':     '^BSESN',
    'UK':        '^FTSE',
    'Germany':   '^GDAXI',
    'Japan':     '^N225',
    'France':    '^FCHI',
    'HongKong':  '^HSI',
    'Brazil':    '^BVSP',
    'Canada':    '^GSPTSE',
    'Australia': '^AXJO'
}

START_DATE      = '2006-01-01'
END_DATE        = '2026-01-01'
INITIAL_CAPITAL = 1_000_000
MAX_SHORT       = 0.10        # max 10% of portfolio in short position
MIN_CAPITAL     = 100         # minimum $100 needed to trade


#Download & Clean Data 
raw_data   = yf.download(list(INDEXES.values()), start=START_DATE, end=END_DATE, auto_adjust=True)
Close_data = raw_data['Close']
Close_data.columns = list(INDEXES.keys())
Close_data = Close_data.ffill().bfill()


#EMA calculations
def calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

#RSI calculation
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain  = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))

countries        = list(INDEXES.keys())
failed_countries = []

for country in countries:
    try:
        # try/except only here — RSI can fail on zero division
        # if a country has no price movement (loss = 0)
        Close_data[f'{country}_EMA9'] = calculate_ema(Close_data[country], 9)
        Close_data[f'{country}_EMA21'] = calculate_ema(Close_data[country], 21)
        Close_data[f'{country}_RSI']   = calculate_rsi(Close_data[country], 14)
    except Exception as e:
        print(f"⚠️ {country} indicator failed: {e}")
        failed_countries.append(country)

for c in failed_countries:
    countries.remove(c)


#Signals
# Signal values:
#  1 = LONG  (buy)
# -1 = SHORT (bet market goes down, max 10%)
#  0 = CASH  (do nothing)

for country in countries:
    ema9 = Close_data[f'{country}_EMA9']
    ema21 = Close_data[f'{country}_EMA21']
    rsi   = Close_data[f'{country}_RSI']

    
    long_condition  = (ema9 > ema21) & (rsi > 40) & (rsi < 65)

    
    short_condition = (ema9 < ema21) & (rsi > 70)

    Close_data[f'{country}_Signal'] = 0
    Close_data.loc[long_condition,  f'{country}_Signal'] =  1
    Close_data.loc[short_condition, f'{country}_Signal'] = -1


# Portfolio Simulation:
# Dynamic Position Sizing:
#   RSI < 45  -> 80% invested (strong buy opportunity)
#   RSI < 55  -> 60% invested (moderate opportunity)
#   RSI < 65  -> 40% invested (weak opportunity)
#   RSI >= 65 -> 20% invested (very cautious)

portfolio = pd.DataFrame(index=Close_data.index)

for country in countries:
    signal  = Close_data[f'{country}_Signal'].shift(1).fillna(0)
    rsi     = Close_data[f'{country}_RSI'].shift(1).fillna(50)
    returns = Close_data[country].pct_change().fillna(0)

    cash         = INITIAL_CAPITAL
    stock_value  = 0.0
    short_value  = 0.0
    target_alloc = 0.0    # initialized to avoid NameError on day 1

    cash_track  = []
    stock_track = []
    short_track = []
    value_track = []
    strat_track = []
    alloc_track = []
    mode_track  = []

    for i in range(len(Close_data)):
        s = signal.iloc[i]
        r = rsi.iloc[i]
        d = returns.iloc[i]

        total_value = cash + stock_value

        # Guard 1: Portfolio wiped out — stop all trading
        if total_value <= 0:
            cash_track.append(0);  stock_track.append(0)
            short_track.append(0); value_track.append(0)
            strat_track.append(0); alloc_track.append(0)
            mode_track.append('WIPED')
            continue

        # Guard 2: Capital too low — force cash mode
        if total_value < MIN_CAPITAL:
            if stock_value > 0: cash += stock_value; stock_value = 0.0
            if short_value > 0: cash += short_value; short_value = 0.0
            cash_track.append(cash);  stock_track.append(0)
            short_track.append(0);    value_track.append(cash)
            strat_track.append(0);    alloc_track.append(0)
            mode_track.append('CASH')
            continue

        # LONG position logic
        if s == 1:
            if short_value > 0: cash += short_value; short_value = 0.0

            # Dynamic allocation based on RSI strength
            if r < 45:   target_alloc = 0.80
            elif r < 55: target_alloc = 0.60
            elif r < 65: target_alloc = 0.40
            else:        target_alloc = 0.20

            # Rebalance only if drift > 1% of portfolio
            target_stock = total_value * target_alloc
            if abs(target_stock - stock_value) > total_value * 0.01:
                stock_value = target_stock
                cash        = total_value - stock_value
            mode = 'LONG'

        # SHORT position logic
        elif s == -1:
            if stock_value > 0: cash += stock_value; stock_value = 0.0
            target_short = total_value * MAX_SHORT
            if abs(target_short - short_value) > total_value * 0.01:
                short_value = target_short
            target_alloc = -MAX_SHORT
            mode         = 'SHORT'

        # CASH — close all positions
        else:
            if short_value > 0: cash += short_value; short_value = 0.0
            if stock_value > 0: cash += stock_value; stock_value = 0.0
            target_alloc = 0.0
            mode         = 'CASH'

        # Apply market returns
        stock_value = stock_value * (1 + d)  # long gains/loses with market
        short_pnl   = short_value * (-d)      # short profits when market falls
        cash       += short_pnl               # short P&L hits cash daily

        # Guard 3: Margin call — negative cash from short losses
        if cash < 0:
            short_value = 0.0
            cash        = 0.0
            mode        = 'CASH'

        total_value  = cash + stock_value
        strat_return = (total_value - value_track[-1]) / value_track[-1] if i > 0 else 0

        cash_track.append(cash);          stock_track.append(stock_value)
        short_track.append(short_value);  value_track.append(total_value)
        strat_track.append(strat_return); alloc_track.append(target_alloc)
        mode_track.append(mode)

    portfolio[f'{country}_Cash']       = cash_track
    portfolio[f'{country}_InStock']    = stock_track
    portfolio[f'{country}_Short']      = short_track
    portfolio[f'{country}_Value']      = value_track
    portfolio[f'{country}_Strategy']   = strat_track
    portfolio[f'{country}_Allocation'] = alloc_track
    portfolio[f'{country}_Mode']       = mode_track

portfolio = portfolio.ffill().bfill()


#Snapshot Function
def portfolio_snapshot(date=None):
    row = portfolio.iloc[-1] if date is None else portfolio.loc[date]
    print(f"\n📊 Snapshot — {row.name.date()}")
    print("-" * 75)
    print(f"{'Country':<12} {'Total':>11} {'In Stock':>11} {'Short':>11} {'Cash':>11} {'Mode':>7}")
    print("-" * 75)
    total_v = total_s = total_sh = total_c = 0
    for country in countries:
        v  = row[f'{country}_Value'];   s  = row[f'{country}_InStock']
        sh = row[f'{country}_Short'];   c  = row[f'{country}_Cash']
        m  = row[f'{country}_Mode']
        total_v += v; total_s += s; total_sh += sh; total_c += c
        print(f"{country:<12} ${v:>10,.0f} ${s:>10,.0f} ${sh:>10,.0f} ${c:>10,.0f} {m:>7}")
    print("-" * 75)
    print(f"{'TOTAL':<12} ${total_v:>10,.0f} ${total_s:>10,.0f} ${total_sh:>10,.0f} ${total_c:>10,.0f}")
    print(f"\n   Stocks: {total_s/total_v*100:.1f}%  |  Short: {total_sh/total_v*100:.1f}%  |  Cash: {total_c/total_v*100:.1f}%")


#Performance Metrics
metrics = {}

for country in countries:
    strat_ret = pd.Series(portfolio[f'{country}_Strategy']).replace(0, np.nan).dropna()
    port_val  = portfolio[f'{country}_Value']

    total_return = (port_val.iloc[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    sharpe       = (strat_ret.mean() / strat_ret.std()) * np.sqrt(252)
    rolling_max  = port_val.cummax()
    max_drawdown = ((port_val - rolling_max) / rolling_max).min() * 100
    avg_alloc    = portfolio[f'{country}_Allocation'].mean() * 100
    short_days   = int((portfolio[f'{country}_Mode'] == 'SHORT').sum())
    wiped_out    = 'YES' if 'WIPED' in portfolio[f'{country}_Mode'].values else 'NO'

    metrics[country] = {
        'Total Return (%)' : round(total_return, 2),
        'Sharpe Ratio'     : round(sharpe, 2),
        'Max Drawdown (%)' : round(max_drawdown, 2),
        'Avg Alloc (%)'    : round(avg_alloc, 2),
        'Short Days'       : short_days,
        'Wiped Out'        : wiped_out
    }

metrics_df = pd.DataFrame(metrics).T.sort_values('Total Return (%)', ascending=False)

print("\n===== PERFORMANCE METRICS =====")
print(metrics_df)

final_val   = portfolio[[f'{c}_Value'   for c in countries]].iloc[-1].sum()
final_stock = portfolio[[f'{c}_InStock' for c in countries]].iloc[-1].sum()
final_short = portfolio[[f'{c}_Short'   for c in countries]].iloc[-1].sum()
final_cash  = portfolio[[f'{c}_Cash'    for c in countries]].iloc[-1].sum()

print(f"\nBest:  {metrics_df['Total Return (%)'].idxmax()} ({metrics_df['Total Return (%)'].max()}%)")
print(f"Worst: {metrics_df['Total Return (%)'].idxmin()} ({metrics_df['Total Return (%)'].min()}%)")
print(f"\nTotal Portfolio: ${final_val:,.2f}")
print(f"In Stocks:       ${final_stock:,.2f} ({final_stock/final_val*100:.1f}%)")
print(f"Shorted:         ${final_short:,.2f} ({final_short/final_val*100:.1f}%)")
print(f"In Cash:         ${final_cash:,.2f}  ({final_cash/final_val*100:.1f}%)")
print(f"Total Return:    {(final_val - 10_000_000) / 10_000_000 * 100:.2f}%")

portfolio_snapshot()


#Visualization
fig, axes = plt.subplots(2, 2, figsize=(18, 14))
fig.suptitle('EMA + RSI Strategy — 10 Country Portfolio ($1M each)',
             fontsize=16, fontweight='bold', y=0.98)

# Chart 1: Portfolio Value Over Time
ax1 = axes[0, 0]
for country in countries:
    ax1.plot(portfolio.index, portfolio[f'{country}_Value'], label=country, linewidth=1.5)
ax1.axhline(y=INITIAL_CAPITAL, color='black', linestyle='--', linewidth=1, label='Starting Capital')
ax1.set_title('Portfolio Value Over Time')
ax1.set_xlabel('Date')
ax1.set_ylabel('Portfolio Value ($)')
ax1.legend(fontsize=7, ncol=2)
ax1.tick_params(axis='x', rotation=45, pad=5)
ax1.grid(True, alpha=0.3)

# Chart 2: Total Return % per Country
ax2 = axes[0, 1]
vals   = metrics_df['Total Return (%)'].astype(float)
colors = ['green' if x > 0 else 'red' for x in vals]
bars   = ax2.bar(metrics_df.index, vals, color=colors, edgecolor='black', alpha=0.8)
ax2.axhline(y=0, color='black', linewidth=0.8)
ax2.set_title('Total Return % per Country (Best to Worst)')
ax2.set_ylabel('Return (%)')
ax2.tick_params(axis='x', rotation=45, pad=5)
ax2.grid(True, alpha=0.3, axis='y')
for bar, val in zip(bars, vals):
    ax2.text(bar.get_x() + bar.get_width()/2,
             bar.get_height() + 0.3 if val >= 0 else bar.get_height() - 1.5,
             f'{val:.1f}%', ha='center', va='bottom', fontsize=8)

# Chart 3: Sharpe Ratio per Country
ax3 = axes[1, 0]
sharpe_vals = metrics_df['Sharpe Ratio'].astype(float)
colors2     = ['green' if x > 0 else 'red' for x in sharpe_vals]
ax3.bar(metrics_df.index, sharpe_vals, color=colors2, edgecolor='black', alpha=0.8)
ax3.axhline(y=0, color='black', linewidth=0.8)
ax3.axhline(y=1, color='green', linewidth=1, linestyle='--', label='Good (>1.0)')
ax3.axhline(y=2, color='blue',  linewidth=1, linestyle='--', label='Great (>2.0)')
ax3.set_title('Sharpe Ratio per Country')
ax3.set_ylabel('Sharpe Ratio')
ax3.tick_params(axis='x', rotation=45, pad=5)
ax3.legend()
ax3.grid(True, alpha=0.3, axis='y')

# Chart 4: Max Drawdown per Country
ax4 = axes[1, 1]
dd_vals = metrics_df['Max Drawdown (%)'].astype(float)
bars3   = ax4.bar(metrics_df.index, dd_vals, color='orange', edgecolor='black', alpha=0.8)
ax4.set_title('Max Drawdown % per Country (closer to 0 = better)')
ax4.set_ylabel('Max Drawdown (%)')
ax4.tick_params(axis='x', rotation=45, pad=5)
ax4.grid(True, alpha=0.3, axis='y')
for bar, val in zip(bars3, dd_vals):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() - 0.5,
             f'{val:.1f}%', ha='center', va='top', fontsize=8)

plt.subplots_adjust(top=0.90, bottom=0.12, hspace=0.55, wspace=0.35)
plt.savefig('portfolio_analysis.png', dpi=150, bbox_inches='tight')
plt.show()