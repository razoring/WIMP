import discord
from discord.ext import commands
from discord import app_commands
import os
import typing
from projections import project
from dotenv import load_dotenv

from themes import brand, bgDark

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(intents=intents, command_prefix="!")

@bot.event
async def on_ready():
    await bot.tree.sync()

@bot.tree.command(name="help", description="Prints debug information.")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(f"Responsive Investment Calculation Heuristic (R.I.C.H.)")

@bot.tree.command(name="predict", description="Predicts future movements of a given ticker")
@app_commands.describe(ticker="The ticker symbol to predict (ex. AAPL)", duration="How many days to predict", model="Choose model efficiency")
@app_commands.choices(duration=[
    app_commands.Choice(name="30 days", value="30"),
    app_commands.Choice(name="60 days", value="60"),
    app_commands.Choice(name="90 days", value="90")])
@app_commands.choices(model=[
    app_commands.Choice(name="Options Volatility (≤3s)", value="0"),
    app_commands.Choice(name="Algorithmic Analysis (≤2m)", value="1"),
    app_commands.Choice(name="Reasoning AI Analysis [UNAVAILABLE] (≤5m)", value="2")])
async def predict(interaction: discord.Interaction, ticker: str, duration: typing.Optional[app_commands.Choice[str]], model: typing.Optional[app_commands.Choice[str]]):
    await interaction.response.defer()

    embed = discord.Embed(color=discord.Colour.teal())
    embed.set_footer(text="Disclaimer: Projections are not guarantees of future price movements and may differ from actual performance. Trade responsibly. Not financial advice.")

    try:
        image_buffer = project(ticker, duration.value if duration != None else 90, model.value if model != None else 0)
        if image_buffer:
            file = discord.File(image_buffer, filename="output.png")
            embed.set_image(url="attachment://output.png")
            await interaction.followup.send(file=file, embed=embed)
        else:
            await interaction.followup.send("```ERROR: Please check you entered the ticker symbol correct.```")
    except Exception as e:
        await interaction.followup.send(f"```FATAL ERROR: {e}```")

bot.run(TOKEN)