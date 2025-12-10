import io
import doctest

import numpy as np
import pandas as pd
import yfinance as yf

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import LinearLocator, FormatStrFormatter
from matplotlib.patches import Polygon
from matplotlib.colors import LinearSegmentedColormap, to_rgba

from scipy.interpolate import CubicSpline
from scipy.stats import norm
from datetime import datetime, timedelta

from prophet import Prophet as ph

from themes import brand, bgDark
# end of imports

matplotlib.use("Agg") # set backend / disables ui opening
#matplotlib.rc("font", family="Courier New")
#plt.rcParams["font.family"] = "sans-serif"
#plt.rcParams["font.sans-serif"] = ["Helvetica"]
#plt.rcParams["font.style"] = "oblique"
#plt.style.use("dark_background")
plt.rc("font", weight="bold", size=10)

def ivSmoothing(stock, lastDate, forward, curPrice, quantiles, futureDays):
    anchorsY = [[curPrice] * len(quantiles)] # [days forward, [prices at quartiles]]
    anchorsX = [0]

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
    
    smoothing = []
    for quantile_series in yTransposed:
        # "natural" boundary conditions for smooth start/end
        cs = CubicSpline(anchorsX, quantile_series, bc_type="natural")
        smoothing.append(cs(futureDays))
    return np.array(smoothing)

def project(ticker, forward, model):
    # typecasting (caused all the model errors)
    model = int(model) if type(model) == str else 0
    forward = int(forward) if type(model) == str else 90

    stock = yf.Ticker(ticker)
    history = stock.history(period="1mo") if model == 0 else stock.history(period="1y")
    if history.empty:
        return None
    
    curPrice = history["Close"].iloc[-1]
    lastDate = history.index[-1]
    plotHistory = history[history.index > lastDate - timedelta(days=7)]
    quantiles = np.linspace(0.05, 0.95, 19) # 19 divisons

    futureDays = np.arange(0, forward + 1)
    futureDates = [lastDate + timedelta(days=int(d)) for d in futureDays]
    
    smoothing = []
    # Prophet predictions
    prophetTrend = None
    prophetSigma = None
    if model != 0: # not model IV
        prophetData = history.reset_index()[["Date", "Close"]]
        prophetData.columns = ["ds", "y"]
        prophetData["ds"] = prophetData["ds"].dt.tz_localize(None)

        mProphet = ph(daily_seasonality=True, yearly_seasonality=True)
        mProphet.fit(prophetData)

        futureProphet = mProphet.make_future_dataframe(periods=forward, freq='D') # match freq
        fcst = mProphet.predict(futureProphet)

        futureFcst = fcst.tail(forward + 1)
        prophetTrend = futureFcst["yhat"].values
        prophetTrend += curPrice - prophetTrend[0]
        
        upper = futureFcst["yhat_upper"].values*0 #affect the fan graph
        lower = futureFcst["yhat_lower"].values*0
        prophetSigma = (upper - lower) / 2.56 # 80% confidence interval width / 2.56 ~= 1 standard deviation

    # IV calulcations
    if model != 1: # not model prophet
        smoothing = ivSmoothing(stock=stock,lastDate=lastDate,forward=forward,curPrice=curPrice,quantiles=quantiles, futureDays=futureDays)

    if model == 1:
        if prophetTrend is None:
            raise "Prophet is NoneType"
            
        tempSmoothing = []
        for q in quantiles:
            z = norm.ppf(q)
            line = prophetTrend + (z * prophetSigma)
            tempSmoothing.append(line)
        smoothing = np.array(tempSmoothing)
    elif model == 2:
        if prophetTrend is None:
            pass 
        else:
            spread = smoothing - curPrice 
            combinedSmoothing = []
            for i in range(len(quantiles)):
                combinedSmoothing.append(prophetTrend + spread[i])
            smoothing = np.array(combinedSmoothing)

    # plot the graph
    fig, ax = plt.subplots(figsize=(20, 10), dpi=120)
    fig.patch.set_facecolor(color=bgDark)
    ax.plot(plotHistory.index, plotHistory["Close"], color=brand, linewidth=2, zorder=10)
    minY = min(plotHistory["Close"].min(), np.min(smoothing))
    maxY = max(plotHistory["Close"].max(), np.max(smoothing))
    xNums = mdates.date2num(plotHistory.index)
    yVals = plotHistory["Close"].values
    yFloor = minY * 0.90
    
    #gradient logic
    verts = [(xNums[0], yFloor)] + list(zip(xNums, yVals)) + [(xNums[-1], yFloor)]
    poly = Polygon(verts, transform=ax.transData, facecolor='none', edgecolor='none')
    ax.add_patch(poly)
    cTop = to_rgba(brand, alpha=0.3)
    cBot = to_rgba(brand, alpha=0.0)
    gradientCmap = LinearSegmentedColormap.from_list('history_gradient', [cBot, cTop])
    gradient = np.linspace(0, 1, 256).reshape(-1, 1)
    im = ax.imshow(gradient, aspect='auto', cmap=gradientCmap, origin='lower', extent=[xNums[0], xNums[-1], yFloor, yVals.max()], zorder=1)
    im.set_clip_path(poly)
    
    mid = len(quantiles) // 2
    for i in range(mid):
        lower_curve = smoothing[i]
        upper_curve = smoothing[-(i+1)]
        ax.fill_between(futureDates, lower_curve, upper_curve, color=brand, alpha=0.15, lw=0)

    # 50% line
    median = smoothing[mid] # make them start at the same spot
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
    dates = list(plotHistory.index) + futureDates
    plt.xlim(dates[0], dates[-1])

    plt.tight_layout()
    # save to memory buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0) # rewind buffer
    
    return buf

if __name__ == "__main__":
    doctest.testmod()