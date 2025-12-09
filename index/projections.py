import io
import numpy as np
import pandas as pd
import yfinance as yf

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import LinearLocator, FormatStrFormatter

from scipy.interpolate import CubicSpline
from scipy.stats import norm
from datetime import datetime, timedelta

import prophet as ph

from themes import brand, bgDark


matplotlib.use("Agg") # set backend / disables ui opening
#matplotlib.rc("font", family="Courier New")
#plt.rcParams["font.family"] = "sans-serif"
#plt.rcParams["font.sans-serif"] = ["Helvetica"]
#plt.rcParams["font.style"] = "oblique"
#plt.style.use("dark_background")
plt.rc("font", weight="bold", size=10)

def project(ticker, forward=90, model=0):
    stock = yf.Ticker(ticker)
    history = stock.history(interval="1wk")
    
    if history.empty:
        return None

    curPrice = history["Close"].iloc[-1]
    lastDate = history.index[-1]
    
    # IV calulcations
    quantiles = np.linspace(0.05, 0.95, 19) # 19 divison
    
    # [days forward, [prices at quartiles]]
    anchorsX = [0]
    anchorsY = [[curPrice] * len(quantiles)] 
    
    # Loop expirations
    for exp in stock.options: # Stock options = expirationjs
        try:
            expDate = datetime.strptime(exp, "%Y-%m-%d").date()
            expDays = (expDate - lastDate.date()).days
            
            if expDays <= 0: continue
            if expDays > forward + 15: break # don"t calculate too far out
            
            opt = stock.option_chain(exp)
            calls = opt.calls
            puts = opt.puts
            
            # ATM (At the Money) IV
            centerStrike = curPrice
            callsATM = calls.iloc[(calls["strike"] - centerStrike).abs().argsort()[:2]]
            putsATM = puts.iloc[(puts["strike"] - centerStrike).abs().argsort()[:2]]
            
            merged = pd.concat([callsATM["impliedVolatility"], putsATM["impliedVolatility"]])
            mean = merged.mean()
            
            if np.isnan(mean) or mean == 0: continue

            # calculate distribution
            tYears = expDays / 365.0
            expPrices = []
            for q in quantiles:
                z = norm.ppf(q)
                # geometric brownian motion calculation
                projection = curPrice*np.exp(-1*mean**2 * tYears+mean * np.sqrt(tYears)*z) #-0.5*mean**2 * tYears+mean * np.sqrt(tYears)*z
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
    futureDates = [lastDate + timedelta(days=int(d)) for d in futureDays]
    
    smoothing = []
    for quantile_series in yTransposed:
        # "natural" boundary conditions for smooth start/end
        cs = CubicSpline(anchorsX, quantile_series, bc_type="natural")
        smoothing.append(cs(futureDays))
        
    smoothing = np.array(smoothing)
    

    # plot the graph
    fig, ax = plt.subplots(figsize=(20, 10), dpi=120)
    fig.patch.set_facecolor(color=bgDark)
    ax.plot(history.index, history["Close"], color=brand, linewidth=2, zorder=10)
    minY = min(history["Close"].min(), np.min(smoothing))
    maxY = max(history["Close"].max(), np.max(smoothing))
    ax.fill_between(history.index, minY * 0.90, history["Close"], color=brand, alpha=0.2)
    
    # start fan graph
    mid = len(quantiles) // 2
    for i in range(mid):
        lower_curve = smoothing[i]
        upper_curve = smoothing[-(i+1)]
        ax.fill_between(futureDates, lower_curve, upper_curve, color=brand, alpha=0.15, lw=0)

    # 50% line
    median = smoothing[mid]
    ax.plot(futureDates, median, color=brand, linewidth=2)

    # labels
    ax = plt.gca()
    ax.set_facecolor(bgDark)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.tick_params(axis="x", rotation=90, colors="gray")
    #plt.setp(ax.get_xticklabels(), weight="bold")

    ax.yaxis.set_major_locator(LinearLocator(numticks=30))
    ax.yaxis.set_major_formatter(FormatStrFormatter("$%.2f"))
    ax.tick_params(axis="y", colors="gray")
    #plt.setp(ax.get_yticklabels(), weight="bold")

    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.tick_params(colors='gray', which='both')
    #ax.text(futureDates[-1], median[-1], f" ${median[-1]:.2f}", color=colour, fontweight='bold', fontsize=11, va='center', ha='left')
    bbox = dict(boxstyle="square,pad=0.3", fc=bgDark, ec="none", alpha=1.0)
    ax.annotate(f"${median[-1]:.2f}", xy=(1, median[-1]), xycoords=('axes fraction', 'data'), xytext=(5, 0), textcoords='offset points', va='center', ha='left', color=brand, fontweight='bold', fontsize=11, bbox=bbox,)

    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines['right'].set_color("gray")
    ax.spines['bottom'].set_color("gray")
    
    # grid
    ax.grid(True, which="major", axis="y", linestyle="--", alpha=0.5)
    ax.grid(True, which="major", axis="x", linestyle=":", alpha=0.3) # added x-grid to see days better
    plt.ylim(minY * 0.98, maxY * 1.02)
    
    # combine both line and fan graphs
    dates = list(history.index) + futureDates
    plt.xlim(dates[0], dates[-1])

    plt.tight_layout()
    # save to memory buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0) # rewind buffer
    
    return buf