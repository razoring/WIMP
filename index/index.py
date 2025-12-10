import os
import typing
from dotenv import load_dotenv
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

import yfinance as yf
import pandas as pd
from humanize import numSuffix

from projections import project
from themes import brand, bgDark

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(intents=intents, command_prefix="!")

models = ["Implied Volatility", "Extrapolation", "Aggregate-Extrapolation", "Logical Analysis [UNAVAILABLE]"]

@bot.event
async def on_ready():
    await bot.tree.sync()

@bot.tree.command(name="help", description="Prints debug information.")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(f"Responsive Investment Calculation Heuristic (R.I.C.H.)")

@bot.tree.command(name="predict", description="Predicts future movements of a given ticker")
@app_commands.describe(ticker="The ticker symbol to predict (ex. AAPL)", model="Choose model algorithm")
@app_commands.choices(model=[
    app_commands.Choice(name=models[0], value="0"),
    app_commands.Choice(name=models[1], value="1"),
    app_commands.Choice(name=models[2], value="2"),
    app_commands.Choice(name=models[3], value="3")])
async def predict(interaction: discord.Interaction, ticker: str, model: typing.Optional[app_commands.Choice[str]]):
    await interaction.response.defer()

    embed = discord.Embed(color=discord.Colour.teal(), title=f"{ticker} (90 day prediction)")
    #embed.set_footer(text=f"{interaction.user.mention}")
    if type(model) is not type(None):
        selectedModel = int(model.value)
    else:
        selectedModel = 2

    image_buffer = project(ticker, selectedModel)
    if image_buffer:
        file = discord.File(image_buffer, filename="output.png")

        symbol = yf.Ticker(ticker)
        history = symbol.history(period="1d")
        year = symbol.history(period="1y")
        info = symbol.info

        # yield courtesy of: https://www.khueapps.com/blog/article/how-to-fetch-stock-dividend-data-with-python
        div = symbol.dividends
        now = pd.Timestamp.utcnow().tz_localize(None)
        yearAgo = now - pd.DateOffset(years=1)
        close = yf.Ticker(ticker).history(period="5d")["Close"].iloc[-1]
        yearAgo = pd.Timestamp(yearAgo, tz=div.index.tz)
        ttmDiv = div[div.index >= yearAgo].sum()
        yields = 100.0 * ttmDiv / close if close > 0 else float("nan")

        embed.set_image(url="attachment://output.png")
        embed.add_field(name=f"High: ${round(history['High'].max(),2)}", value=f"Low: ${round(history['Low'].min(),2)}", inline=True)
        embed.add_field(name=f"Open: ${round(history['Open'].max(),2)}", value=f"Close: ${round(history['Close'].max(),2)}", inline=True)
        embed.add_field(name=f"Vol: {numSuffix(round(history['Volume'].max(),2))}", value=f"Beta: {numSuffix(round(symbol.info.get('beta', 0),2))}", inline=True)
        embed.add_field(name=f"52Wk High: ${round(year['High'].max(),2)}", value=f"52Wk Low: ${round(year['Low'].min(),2)}", inline=True)
        embed.add_field(name=f"P/E: ${round(info.get('trailingPE', 0),2)}", value=f"EPS: ${round(symbol.info.get('trailingEps'),2)}", inline=True)
        embed.add_field(name=f"Yield: {round(yields,2)}%", value=f"Ex. Dividend: {datetime.fromtimestamp(info.get('exDividendDate'))}", inline=True)

        await interaction.followup.send(f"Here is today's predictions ({models[int(selectedModel)]} Model) {interaction.user.mention}:",file=file, embed=embed)
    else:
        await interaction.followup.send("```ERROR: Please check you entered the ticker symbol correct.```")

bot.run(TOKEN)