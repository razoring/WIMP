import discord
from discord.ext import commands
from discord import app_commands
import os
from projections import project
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(intents=intents, command_prefix="!")

@bot.event
async def on_ready():
    await bot.tree.sync()

@bot.tree.command(name="status", description="Prints debug information.")
async def status(interaction: discord.Interaction):
    await interaction.response.send_message(f"Responsive Investment Calculation Heuristic (R.I.C.H.)")

@bot.tree.command(name="predict", description="Predicts future movements of a given ticker")
@app_commands.describe(ticker="The ticker symbol to predict (ex. AAPL, MSFT, GOOG)", duration="How many days to predict")
@app_commands.choices(duration=[
    app_commands.Choice(name="1 month", value="30"),
    app_commands.Choice(name="2 months", value="60"),
    app_commands.Choice(name="3 months", value="90")])
async def predict(interaction: discord.Interaction, ticker: str, duration: app_commands.Choice[str]):
    try:
        await interaction.response.defer()
        image_buffer = project(ticker, int(duration.value))
        file = discord.File(image_buffer, filename="output.png")
        embed = discord.Embed()
        embed.set_image(url="attachment://output.png")
        await interaction.followup.send(file=file, embed=embed)
    except:
        await interaction.response.send_message("Sorry, we could not fulfill your request at this time. Please try again in a few seconds.")

bot.run(TOKEN)