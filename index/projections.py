import io
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import LinearLocator, FormatStrFormatter
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.interpolate import CubicSpline
from scipy.stats import norm
from datetime import datetime, timedelta

matplotlib.use('Agg') # set backend / disables ui opening
matplotlib.rcParams['font.family'] = 'monospace' # set globalfont

def project(ticker, forward=90):
    stock = yf.Ticker(ticker)
    
    history = stock.history(period="1mo")
    
    if history.empty:
        raise ValueError("Could not fetch data for ticker.")

    curPrice = history['Close'].iloc[-1]
    lastDate = history.index[-1]
    
    # IV calulcations
    quantiles = np.linspace(0.05, 0.95, 25) # 19 layers for gradient
    
    # [days forward, [prices at quartiles]]
    anchorsX = [0]
    anchorsY = [[curPrice] * len(quantiles)] 
    
    # Loop expirations
    for exp in stock.options: # Stock options = expirationjs
        try:
            expDate = datetime.strptime(exp, "%Y-%m-%d").date()
            expDays = (expDate - lastDate.date()).days
            
            if expDays <= 0: continue
            if expDays > forward + 15: break # don't calculate too far out
            
            opt = stock.option_chain(exp)
            calls = opt.calls
            puts = opt.puts
            
            # ATM (At the Money) IV
            centerStrike = curPrice
            callsATM = calls.iloc[(calls['strike'] - centerStrike).abs().argsort()[:2]]
            putsATM = puts.iloc[(puts['strike'] - centerStrike).abs().argsort()[:2]]
            
            merged = pd.concat([callsATM['impliedVolatility'], putsATM['impliedVolatility']])
            mean = merged.mean()
            
            if np.isnan(mean) or mean == 0: continue

            # calculate distribution
            tYears = expDays / 365.0
            expPrices = []
            for q in quantiles:
                z = norm.ppf(q)
                # geometric brownian motion calculation
                projection = curPrice*np.exp(-0.5*mean**2 * tYears+mean * np.sqrt(tYears)*z)
                expPrices.append(projection)
            
            anchorsX.append(expDays)
            anchorsY.append(expPrices)
        except Exception:
            continue

    # begin interpolation
    if len(anchorsX) < 2:
        # Fallback if no options data found
        anchorsX.append(forward)
        anchorsY.append([curPrice] * len(quantiles))

    yTransposed = np.array(anchorsY).T 
    futureDays = np.arange(0, forward + 1)
    future_dates = [lastDate + timedelta(days=int(d)) for d in futureDays]
    
    smoothing = []
    for quantile_series in yTransposed:
        # 'natural' boundary conditions for smooth start/end
        cs = CubicSpline(anchorsX, quantile_series, bc_type='natural')
        smoothing.append(cs(futureDays))
        
    smoothing = np.array(smoothing)
    

    # plot the graph
    fig, ax = plt.subplots(figsize=(16, 10), dpi=100)
    ax.plot(history.index, history['Close'], color='#0055ff', linewidth=2, zorder=10)
    minY = min(history['Close'].min(), np.min(smoothing))
    maxY = max(history['Close'].max(), np.max(smoothing))
    ax.fill_between(history.index, minY * 0.90, history['Close'], color='#4da6ff', alpha=0.4)
    
    # start fan graph
    mid = len(quantiles) // 2
    for i in range(mid):
        lower_curve = smoothing[i]
        upper_curve = smoothing[-(i+1)]
        ax.fill_between(future_dates, lower_curve, upper_curve, color='#4da6ff', alpha=0.10, lw=0)

    # 50% line
    median = smoothing[mid]
    ax.plot(future_dates, median, color='#0055ff', linewidth=2)

    # labels
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.xticks(rotation=90,fontsize=8)

    ax.yaxis.set_major_locator(LinearLocator(numticks=40))
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
    ax.tick_params(axis='y',labelsize=8)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")

    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_visible(False)
    
    # grid
    ax.grid(True, which='major', axis='y', linestyle='--', alpha=0.5)
    ax.grid(True, which='major', axis='x', linestyle=':', alpha=0.3) # added x-grid to see days better
    plt.ylim(minY * 0.98, maxY * 1.02)
    
    # combine both line and fan graphs
    dates = list(history.index) + future_dates
    plt.xlim(dates[0], dates[-1])

    plt.tight_layout()
    # save to memory buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0) # rewind buffer
    
    return buf