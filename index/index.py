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

@bot.event
async def on_ready():
    await bot.tree.sync()

@bot.tree.command(name="help", description="Prints debug information.")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(f"Responsive Investment Calculation Heuristic (R.I.C.H.)")

@bot.tree.command(name="predict", description="Predicts future movements of a given ticker")
@app_commands.describe(ticker="The ticker symbol to predict (ex. AAPL)", model="Choose model algorithm")
@app_commands.choices(model=[
    app_commands.Choice(name="Implied Volatility", value="0"),
    app_commands.Choice(name="Extrapolation", value="1"),
    app_commands.Choice(name="Aggregate-Extrapolation", value="2"),
    app_commands.Choice(name="Logical Analysis [UNAVAILABLE]", value="3")])
async def predict(interaction: discord.Interaction, ticker: str, model: typing.Optional[app_commands.Choice[str]]):
    await interaction.response.defer()

    embed = discord.Embed(color=discord.Colour.teal())
    embed.set_footer(text=f"{interaction.user.mention}")

    try:
        image_buffer = project(ticker, model.value if model != None else 2)
        if image_buffer:
            file = discord.File(image_buffer, filename="output.png")
            embed.set_image(url="attachment://output.png")
            await interaction.followup.send(file=file, embed=embed)
        else:
            await interaction.followup.send("```ERROR: Please check you entered the ticker symbol correct.```")
    except Exception as e:
        await interaction.followup.send(f"```FATAL ERROR: {e}```")

bot.run(TOKEN)