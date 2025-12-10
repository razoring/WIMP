import discord
from discord.ext import commands
from discord import app_commands
import os
import typing
from projections import project
#from projections_test import project
from dotenv import load_dotenv

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

    try:
        selectedModel = int(model.value) if model is None else 2
        image_buffer = project(ticker, selectedModel)
        if image_buffer:
            file = discord.File(image_buffer, filename="output.png")
            embed.set_image(url="attachment://output.png")
            embed.add_field(name="High: $999.99", value="Low: $999.99", inline=True)
            embed.add_field(name="Open: $999.99", value="Close: 99T", inline=True)
            embed.add_field(name="Vol: 99M", value="Avg Vol: 99M", inline=True)
            embed.add_field(name="52WK High: 99", value="52WK Low: 99", inline=True)
            embed.add_field(name="P/E: $999", value="EPS: $99", inline=True)
            embed.add_field(name="Yield: 0.09%", value="Ex. Dividend Date: 09/09/29", inline=True)
            await interaction.followup.send(f"Here is today's predictions ({models[int(selectedModel)]}) {interaction.user.mention}:",file=file, embed=embed)
        else:
            await interaction.followup.send("```ERROR: Please check you entered the ticker symbol correct.```")
    except Exception as e:
        await interaction.followup.send(f"```FATAL ERROR: {e}```")

bot.run(TOKEN)