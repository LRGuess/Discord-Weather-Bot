"""
Copyright (c) 2023 K-Bean Studios

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

You may not distribute or modify this script without proper credit to K-Bean Studios.
"""
import discord
from discord import app_commands
from discord.ui import Select, View
from discord.ext import tasks, commands
import pytz
from pytz import all_timezones
import requests
import datetime
from dotenv import load_dotenv
import os
import json

# Define the base directory as the directory where the script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define the path to the data file
DATA_FILE = os.path.join(BASE_DIR, '../Server/user_data.json')

authorized_user_id = 971538245320081508

# Load environment variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENWEATHERMAP_API_KEY = os.getenv('OPENWEATHERMAP_API_KEY')


# Create an instance of Intents
intents = discord.Intents.default()

# Create an instance of the bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary to store user default locations (user_id: location)
default_locations = {}

# Dictionary to store user default temperature units (user_id: unit)
default_units = {}

# Dictionary to store user daily update times (user_id: time)
daily_update_times = {}

# Dictionary to store format preferences for each user
format_preferences = {}

# Generate a list of all available time zones from pytz
timezones_list = pytz.all_timezones

# Set to track users who have received the update in the current minute
sent_updates = set()

def read_data():
    try:
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def write_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

# Global data storage
data = read_data()

#Function to convert to local time
def convert_to_local_time(timestamp, timezone):
    utc_time = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    local_time = utc_time.astimezone(pytz.timezone(timezone))
    return local_time.strftime('%Y-%m-%d %H:%M:%S')
class DateSelectView16(discord.ui.View):
    def __init__(self, forecast_list, location):
        super().__init__(timeout=None)
        self.forecast_list = forecast_list
        self.location = location

        # Create a unique and sorted set of dates
        unique_dates = sorted({datetime.datetime.utcfromtimestamp(forecast['dt']).strftime('%Y-%m-%d') for forecast in forecast_list})

        options = [discord.SelectOption(label=date) for date in unique_dates]
        self.add_item(DateSelect16(options, forecast_list, location))

class DateSelect16(discord.ui.Select):
    def __init__(self, options, forecast_list, location):
        super().__init__(placeholder="Choose a date", min_values=1, max_values=1, options=options)
        self.forecast_list = forecast_list
        self.location = location

    async def callback(self, interaction: discord.Interaction):
        selected_date = self.values[0]
        forecasts_for_date = [forecast for forecast in self.forecast_list if datetime.datetime.utcfromtimestamp(forecast['dt']).strftime('%Y-%m-%d') == selected_date]
        
        forecast_message = f'Forecast for {selected_date}\n\n'
        for forecast in forecasts_for_date:
            forecast_time = datetime.datetime.utcfromtimestamp(forecast['dt']).strftime('%H:%M:%S')
            temperature = forecast['temp']['day'] - 273.15
            description = forecast['weather'][0]['description']
            forecast_message += f'{forecast_time}: Temp: {temperature:.2f}°C, Weather: {description}\n'

        await interaction.response.edit_message(content=forecast_message, view=None)

class DateSelectView(discord.ui.View):
    def __init__(self, forecast_list, location):
        super().__init__(timeout=None)
        self.forecast_list = forecast_list
        self.location = location

        # Create a unique and sorted set of dates
        unique_dates = sorted({datetime.datetime.utcfromtimestamp(forecast['dt']).strftime('%Y-%m-%d') for forecast in forecast_list})

        options = [discord.SelectOption(label=date) for date in unique_dates]
        self.add_item(DateSelect(options, forecast_list, location))

class DateSelect(discord.ui.Select):
    def __init__(self, options, forecast_list, location):
        super().__init__(placeholder="Choose a date", min_values=1, max_values=1, options=options)
        self.forecast_list = forecast_list
        self.location = location

    async def callback(self, interaction: discord.Interaction):
        selected_date = self.values[0]
        forecasts_for_date = [forecast for forecast in self.forecast_list if datetime.datetime.utcfromtimestamp(forecast['dt']).strftime('%Y-%m-%d') == selected_date]
        
        forecast_message = f'Forecast for {selected_date}\n\n'
        for forecast in forecasts_for_date:
            forecast_time = datetime.datetime.utcfromtimestamp(forecast['dt']).strftime('%H:%M:%S')
            temperature = forecast['main']['temp'] - 273.15
            description = forecast['weather'][0]['description']
            forecast_message += f'{forecast_time}: Temp: {temperature:.2f}°C, Weather: {description}\n'

        await interaction.response.edit_message(content=forecast_message, view=None)

# Command to get the weather
@bot.tree.command(name="weather", description="Get the current weather for a location")
async def get_weather(ctx: discord.Interaction, *, location: str = None):
    await ctx.response.defer()


    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})
    default_location = user_data.get('location')
    default_unit = user_data.get('unit', 'C')
    format_preference = user_data.get('format', 'embed')

    if location is None:
        location = default_location

    if location is None:
        if format_preference.lower() == 'plain':
            await ctx.followup.send("Please provide a location or set a default location using /setlocation.")
        else:
            embed = discord.Embed(title='Error', description="Please provide a location or set a default location using /setlocation.")
            await ctx.followup.send(embed=embed)
        return

    weather_api_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
    response = requests.get(weather_api_url)
    weather_data = response.json()

    if response.status_code == 200:
        main_weather = weather_data['weather'][0]['main']
        description = weather_data['weather'][0]['description']
        temperature_main = weather_data['main']['temp']
        temperature = temperature_main - 273.15

        if default_unit == 'F':
            temperature = (temperature_main - 273.15) * 9/5 + 32

        if format_preference.lower() == 'plain':
            await ctx.followup.send(f'The weather in {location} is {main_weather} ({description}) with a temperature of {temperature:.2f}°{"F" if default_unit == "F" else "C"}.')
        else:
            embed = discord.Embed(title=f"Weather in {location}", description=f"{main_weather} ({description}) with a temperature of {temperature:.2f}°{'F' if default_unit == 'F' else 'C'}")
            await ctx.followup.send(embed=embed)
    else:
        await ctx.followup.send(f"Unable to fetch weather data for {location}. Please check the location and try again.")

# Command to set a default location
@bot.tree.command(name="setlocation", description="Set a default location for weather updates")
async def set_location(ctx: discord.Interaction, *, location: str):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    if user_id not in data:
        data[user_id] = {}

    data[user_id]['location'] = location
    write_data(data)

    format_preference = data[user_id].get('format', 'embed')

    if format_preference.lower() == 'plain':
        await ctx.followup.send(f'Default location set to {location}')
    else:
        embed = discord.Embed(title="Setting location", description=f'Default location set to {location}')
        await ctx.followup.send(embed=embed)

# Command to set a default temperature unit
@bot.tree.command(name="setunit", description="Set a default temperature unit (C or F)")
async def set_unit(ctx: discord.Interaction, unit: str):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    format_preference = data[user_id].get('format', 'embed')
    unit = unit.upper()

    if user_id not in data:
        data[user_id] = {}

    if unit in ['C', 'F']:
        data[user_id]['unit'] = unit
        write_data(data)

        if format_preference.lower() == 'plain':
            await ctx.followup.send(f'Default temperature unit set to {unit}.')
        else:
            embed = discord.Embed(title='Unit set', description=f'Default temperature unit set to {unit}.')
            await ctx.followup.send(embed=embed)
            
    elif unit == "🦅":

        data[user_id]['unit'] = 'F'
        write_data(data)

        if format_preference.lower() == 'plain':
            await ctx.followup.send(f'Default temperature unit set to Freedom Units.')
        else:
            embed = discord.Embed(title='Unit set', description=f'Default temperature unit set to Freedom Units.')
            await ctx.followup.send(embed=embed)

    elif unit.lower() == "freedom" :

        data[user_id]['unit'] = 'F'
        write_data(data)

        if format_preference.lower() == 'plain':
            await ctx.followup.send(f'Default temperature unit set to Freedom Units.')
        else:
            embed = discord.Embed(title='Unit set', description=f'Default temperature unit set to Freedom Units.')
            await ctx.followup.send(embed=embed)

    elif unit.lower() == "logical" :

        data[user_id]['unit'] = 'C'
        write_data(data)

        if format_preference.lower() == 'plain':
            await ctx.followup.send(f'Default temperature unit set to Logical.')
        else:
            embed = discord.Embed(title='Unit set', description=f'Default temperature unit set to Logical.')
            await ctx.followup.send(embed=embed)

    else:
        if format_preference.lower() == 'plain':
            await ctx.followup.send('Invalid unit. Please use C or F.')
        else:
            embed = discord.Embed(title='Unit invalid', description='Invalid unit. Please use C or F.')
            await ctx.followup.send(embed=embed)

# Command to get the wind information
@bot.tree.command(name="wind", description="Get the wind information for a location")
async def get_wind(ctx: discord.Interaction, *, location: str = None):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})
    format_preference = user_data.get('format', 'embed')

    if location is None:
        location = user_data.get('location')

        if not location:
            if format_preference.lower() == 'plain':
                await ctx.followup.send("Please provide a location or set a default location using /setlocation.")
            else:
                embed = discord.Embed(title="Location error", description="Please provide a location or set a default location using /setlocation.")
                await ctx.followup.send(embed=embed)
            return

    weather_api_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
    response = requests.get(weather_api_url)
    weather_data = response.json()

    if response.status_code == 200:
        wind_speed = weather_data['wind']['speed']
        wind_direction = weather_data['wind']['deg']

        if format_preference.lower() == 'plain':
            await ctx.followup.send(f'The wind in {location} is blowing at {wind_speed} m/s in the direction of {wind_direction}°.')
        else:
            embed = discord.Embed(title="Wind", description=f'The wind in {location} is blowing at {wind_speed} m/s in the direction of {wind_direction}°.')
            await ctx.followup.send(embed=embed)
    else:
        if format_preference.lower() == 'plain':
            await ctx.followup.send(f"Unable to fetch wind information for {location}. Please check the location and try again.")
        else:
            embed = discord.Embed(title="Error", description=f"Unable to fetch wind information for {location}. Please check the location and try again.")
            await ctx.followup.send(embed=embed)

# Command to get the humidity information
@bot.tree.command(name="humidity", description="Get the humidity information for a location")
async def get_humidity(ctx: discord.Interaction, *, location: str = None):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})
    format_preference = user_data.get('format', 'embed')

    if location is None:
        location = user_data.get('location')

        if not location:
            if format_preference.lower() == 'plain':
                await ctx.followup.send("Please provide a location or set a default location using /setlocation.")
            else:
                embed = discord.Embed(title="Location error", description="Please provide a location or set a default location using /setlocation.")
                await ctx.followup.send(embed=embed)
            return

    weather_api_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
    response = requests.get(weather_api_url)
    weather_data = response.json()

    if response.status_code == 200:
        humidity = weather_data['main']['humidity']

        if format_preference.lower() == 'plain':
            await ctx.followup.send(f'The humidity in {location} is {humidity}%.')
        else:
            embed = discord.Embed(title="Humidity", description=f'The humidity in {location} is {humidity}%.')
            await ctx.followup.send(embed=embed)
    else:
        if format_preference.lower() == 'plain':
            await ctx.followup.send(f"Unable to fetch humidity information for {location}. Please check the location and try again.")
        else:
            embed = discord.Embed(title="Error", description=f"Unable to fetch humidity information for {location}. Please check the location and try again.")
            await ctx.followup.send(embed=embed)

# Command to get the weather forecast
@bot.tree.command(name="forecast", description="Get the weather forecast for a location")
async def get_forecast(ctx: discord.Interaction, *, location: str = None):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})
    format_preference = user_data.get('format', 'embed')

    if location is None:
        location = user_data.get('location')
        if location is None:
            error_message = "Please provide a location or set a default location using /setlocation."
            if format_preference.lower() == 'plain':
                await ctx.followup.send(error_message)
            else:
                embed = discord.Embed(title="Location error", description=error_message)
                await ctx.followup.send(embed=embed)
            return

    # Call OpenWeatherMap Geocoding API
    geocoding_api_url = f'http://api.openweathermap.org/geo/1.0/direct?q={location}&appid={OPENWEATHERMAP_API_KEY}'
    geocoding_response = requests.get(geocoding_api_url)
    geocoding_data = geocoding_response.json()

    if geocoding_response.status_code != 200 or not geocoding_data:
        error_message = f"Unable to fetch coordinates for {location}. Please check the location and try again."
        if format_preference.lower() == 'plain':
            await ctx.followup.send(error_message)
        else:
            embed = discord.Embed(title="Geocoding error", description=error_message)
            await ctx.followup.send(embed=embed)
        return

    lat = geocoding_data[0]['lat']
    lon = geocoding_data[0]['lon']

    forecast_api_url = f'http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHERMAP_API_KEY}'
    response = requests.get(forecast_api_url)
    forecast_data = response.json()

    if response.status_code == 200:
        forecast_list = forecast_data['list']
        view = DateSelectView(forecast_list, location)
        await ctx.followup.send("Select a date to view the weather forecast:", view=view)
    else:
        error_message = f"Unable to fetch weather forecast for {location}. Please check the location and try again."
        if format_preference.lower() == 'plain':
            await ctx.followup.send(error_message)
        else:
            embed = discord.Embed(title="Forecast error", description=error_message)
            await ctx.followup.send(embed=embed)

    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


# Command to get a 16-day forecast
@bot.tree.command(name="16dayforecast", description="Get a 16-day faorcast without ")
async def get_forecast16(ctx: discord.Interaction, *, location: str = None):
        await ctx.response.defer()

        user_id = str(ctx.user.id)
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        
        user_data = data.get(user_id, {})
        format_preference = user_data.get('format', 'embed')

        if location is None:
            location = user_data.get('location')
            if location is None:
                error_message = "Please provide a location or set a default location using /setlocation."
                if format_preference.lower() == 'plain':
                    await ctx.followup.send(error_message)
                else:
                    embed = discord.Embed(title="Location error", description=error_message)
                    await ctx.followup.send(embed=embed)
                return

        # Call OpenWeatherMap Geocoding API
        geocoding_api_url = f'http://api.openweathermap.org/geo/1.0/direct?q={location}&appid={OPENWEATHERMAP_API_KEY}'
        geocoding_response = requests.get(geocoding_api_url)
        geocoding_data = geocoding_response.json()

        if geocoding_response.status_code != 200 or not geocoding_data:
            error_message = f"Unable to fetch coordinates for {location}. Please check the location and try again."
            if format_preference.lower() == 'plain':
                await ctx.followup.send(error_message)
            else:
                embed = discord.Embed(title="Geocoding error", description=error_message)
                await ctx.followup.send(embed=embed)
            return

        lat = geocoding_data[0]['lat']
        lon = geocoding_data[0]['lon']

        forecast_api_url = f'http://api.openweathermap.org/data/2.5/forecast/daily?lat={lat}&lon={lon}&cnt=16&appid={OPENWEATHERMAP_API_KEY}'

        response = requests.get(forecast_api_url)
        forecast_data = response.json()

        # Check if the API request was successful
        if response.status_code == 200:
            # Extract the forecast data
            forecast_list = forecast_data['list']

            # Format the forecast information
            if format_preference.lower() == 'plain':
                forecast_message = f'16-day weather forecast for {location}:\n'
                for forecast in forecast_list:
                    forecast_date = datetime.datetime.utcfromtimestamp(forecast['dt']).strftime('%Y-%m-%d')
                    temperature = forecast['temp']['day'] - 273.15
                    description = forecast['weather'][0]['description']

                    # Convert temperature to the user's preferred unit
                    if user_data.get('unit') == 'F':
                        temperature = (temperature * 9/5) + 32

                    forecast_message += f'{forecast_date}: Temp: {temperature:.2f}°{"F" if user_data.get("unit") == "F" else "C"}, Weather: {description}\n'
                await ctx.followup.send(forecast_message)
            else:
                view = DateSelectView16(forecast_list, location)
                await ctx.followup.send("Select a date to view the weather forecast:", view=view)
        else:
            error_message = f"Unable to fetch weather forecast for {location}. Please check the location and try again."
            if format_preference.lower() == 'plain':
                await ctx.followup.send(error_message)
            else:
                embed = discord.Embed(title="Forecast error", description=error_message)
                await ctx.followup.send(embed=embed)

        # Save the user data to the file
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)

# Command to get weather alerts for a location
@bot.tree.command(name="alerts", description="Get weather alerts for a location")
async def get_alerts(ctx: discord.Interaction, *, location: str = None):    
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})
    format_preference = user_data.get('format', 'embed')

    if location is None:
        location = user_data.get('location')
        if location is None:
            error_message = "Please provide a location or set a default location using /setlocation."
            if format_preference.lower() == 'plain':
                await ctx.followup.send(error_message)
            else:
                embed = discord.Embed(title="Location error", description=error_message)
                await ctx.followup.send(embed=embed)
            return

    # Call OpenWeatherMap API
    alerts_api_url = f'https://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
    response = requests.get(alerts_api_url)
    weather_data = response.json()

    # Check if the API request was successful
    if response.status_code == 200:
        # Check if there are any weather alerts
        if 'alerts' in weather_data:
            # Extract and display weather alerts
            alerts = weather_data['alerts']
            alert_message = f'Weather alerts for {location}:\n'
            for alert in alerts:
                event = alert['event']
                description = alert['description']
                start_time = datetime.datetime.utcfromtimestamp(alert['start']).strftime('%Y-%m-%d %H:%M:%S UTC')
                end_time = datetime.datetime.utcfromtimestamp(alert['end']).strftime('%Y-%m-%d %H:%M:%S UTC')
                alert_message += f'{event}: {description}\nStart Time: {start_time}\nEnd Time: {end_time}\n\n'

            if format_preference.lower() == 'plain':
                await ctx.followup.send(alert_message)
            else:
                embed = discord.Embed(title="Alerts", description=alert_message)
                await ctx.followup.send(embed=embed)
        else:
            if format_preference.lower() == 'plain':
                await ctx.followup.send(f'No weather alerts for {location}.')
            else:
                embed = discord.Embed(title="No Alerts", description=f'No weather alerts for {location}.')
                await ctx.followup.send(embed=embed)
    else:
        error_message = f"Unable to fetch weather alerts for {location}. Please check the location and try again."
        if format_preference.lower() == 'plain':
            await ctx.followup.send(error_message)
        else:
            embed = discord.Embed(title="Alert Error", description=error_message)
            await ctx.followup.send(embed=embed)

    # Save the user data to the file
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

# Command to set message format preference
@bot.tree.command(name="format", description="Choose message format (embed/plain)")
async def format_message(ctx: discord.Interaction, message_format: str):
    await ctx.response.defer()

    if message_format.lower() in ['embed', 'plain']:
        user_id = str(ctx.user.id)
        data.setdefault(user_id, {})
        data[user_id]['format'] = message_format.lower()

        # Save the user data to the file
        with open('user_data.json', 'w') as f:
            json.dump(data, f)

        await ctx.followup.send(f'Message format preference set to {message_format.lower()}.')
    else:
        await ctx.followup.send('Invalid format. Please choose either "embed" or "plain".')
@bot.tree.command(name="bugreport", description="Submit a bug report or feature request!")
async def bug_report(ctx: discord.Interaction):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})
    format_preference = user_data.get('format', 'embed')
    # Bug report text
    description = "If you have a bug report or feature request, please join the discord! \n https://discord.gg/ZxgqU6MhTT \n\n You can also email \n kbeanstudios@gmail.com"

    # Send the text to the Discord Channel
    if format_preference.lower() == 'plain':
        await ctx.followup.send(description)
    else:
        embed = discord.Embed(title="Bug/Feature Report", description=description)
        await ctx.followup.send(embed=embed)

# Command to get information about the weather bot
@bot.tree.command(name="about", description="Get information about the weather bot")
async def info_command(ctx: discord.Interaction):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})
    format_preference = user_data.get('format', 'embed')
    # Provide a brief description of the bot
    description = "A cool bot that can tell you the weather, forecast, wind, and more! Website and full list of commands here: \n https://kbeanstudios.ca/discordweatherbot. \n You can also run /help\n \n If you want to contribute to the project, have ideas, or need support, join the discord! \n https://discord.gg/ZxgqU6MhTT \n \n **Version:** 4.5.1"

    # Send the bot information to the Discord channel
    if format_preference.lower() == 'plain':
        await ctx.followup.send(description)
    else:
        embed = discord.Embed(title="About", description=description)
        await ctx.followup.send(embed=embed)

# Command to get a full list of commands
@bot.tree.command(name="help", description="Full list of commands")
async def help_command(ctx:discord.Interaction):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})
    format_preference = user_data.get('format', 'embed')

    commandlist = "**/weather** [location] provides weather for specified location 🌥\n \n **/forecast** [location] Retrieve a 5-day 3-hour weather forecast for the specified location 📰 \n \n **/16dayforecast** [location] Retrieve a 16-day weather forecast for the specified location 📃 \n \n **/setlocation** [location] Set your default location for weather updates 📍 \n \n **/setunit** [F or C] Choose between Celsius and FreedomUnits for temperature units 🍁 or 🦅 \n \n **/dailyupdate** [time] Receive a daily weather update at the specified time ⏰ \n \n **/wind** [location] Get detailed information about the wind conditions at a specific location 💨 \n \n **/humidity** [location] Check the current humidity level for a given location 💧 \n \n **/suntimes**[location] Find out the sunrise and sunset times for a particular location 🌞 \n \n **/alerts** [location] Receive any weather alerts or warnings for the specified location :bangbang: \n \n **/format** [embed/plain] Choose between an embedded or plain text format for weather responses 📜 \n \n **/weatherbotabout** Get information about WeatherBot, including version and support details ❓\n \n**/bugreport** Submit a bug report or feature request 🐛 \n \n If you need more support, or want to contribute, join the discord! \n https://discord.gg/ZxgqU6MhTT"

    if format_preference.lower() == 'plain':
        await ctx.followup.send(commandlist)
    else:
        embed = discord.Embed(title="Command list", description=commandlist)
        await ctx.followup.send(embed=embed)

# Command to send a smiley face
@bot.tree.command(name="smiley", description="Send a smiley face haha")
async def smiley_command(ctx:discord.Interaction):
    await ctx.response.defer()

    await ctx.followup.send("😁")

@bot.tree.command(name="updatebot", description="Update bot data from JSON")
async def update_bot(ctx: discord.Interaction):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    if user_id == str(authorized_user_id):
        try:
            with open(DATA_FILE, 'r') as file:
                global data
                data = json.load(file)
                await ctx.followup.send("Bot data updated successfully from JSON.")
        except FileNotFoundError:
            await ctx.followup.send("JSON file not found.")
        except json.JSONDecodeError:
            await ctx.followup.send("Error decoding JSON... Creating empty dictionairy")
            data = {}
            await ctx.channel.send("Data = \{\}")
    else:
        await ctx.followup.send("You are not authorized to use this command.")
        
# Command to set a daily update time with timezone and AM/PM option
@bot.tree.command(name="dailyupdate", description="Set a specific time for daily weather updates, choose AM/PM, and select a timezone")
async def set_daily_update(ctx: discord.Interaction, time: str, am_pm: str, timezone: str):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})

    # Parse the time in 12-hour format with AM/PM
    try:
        time_string = f'{time} {am_pm.upper()}'
        update_time = datetime.datetime.strptime(time_string, '%I:%M %p').time()
    except ValueError:
        await ctx.followup.send('Invalid time format. Please use HH:MM and AM/PM.')
        return

    # Validate the selected timezone
    if timezone not in all_timezones:
        await ctx.followup.send(f'Invalid timezone. Please select a valid timezone.')
        return

    # Save the update time, AM/PM option, and timezone
    user_data['daily_update_time'] = update_time.strftime('%H:%M')
    user_data['timezone'] = timezone
    user_data['am_pm'] = am_pm.upper()
    data[user_id] = user_data
    write_data(data)

    await ctx.followup.send(f'Daily weather update time set to {time} {am_pm.upper()} in {timezone}.')

# Autocomplete function for timezones
@set_daily_update.autocomplete('timezone')
async def timezone_autocomplete(interaction: discord.Interaction, current: str):
    # Provide a list of timezones that match the user's input globally
    matching_timezones = [tz for tz in all_timezones if tz.lower().startswith(current.lower())]
    # Return up to 25 matching timezones globally
    return [discord.app_commands.Choice(name=tz, value=tz) for tz in matching_timezones[:25]]

# Command to turn off daily updates
@bot.tree.command(name="disableupdates", description="Turn off daily weather updates")
async def disable_daily_update(ctx: discord.Interaction):
    await ctx.response.defer()

    user_id = str(ctx.user.id)
    user_data = data.get(user_id, {})

    if 'daily_update_time' in user_data:
        del user_data['daily_update_time']
        del user_data['timezone']
        data[user_id] = user_data
        write_data(data)
        await ctx.followup.send('Daily weather updates have been turned off.')
    else:
        await ctx.followup.send('No daily update is set.')

@tasks.loop(seconds=45)
async def send_daily_updates():
    current_utc_time = datetime.datetime.utcnow().time()
    current_minute = current_utc_time.minute
    for user_id, user_data in data.items():
        try:
            update_time = datetime.datetime.strptime(user_data['daily_update_time'], '%H:%M').time()
            user_tz = pytz.timezone(user_data['timezone'])
            user_local_time = user_tz.localize(datetime.datetime.combine(datetime.date.today(), update_time))
            user_utc_time = user_local_time.astimezone(pytz.utc).time()

            print(f"Checking updates for user {user_id}:")
            print(f"Current UTC time: {current_utc_time}")
            print(f"User's local time: {user_local_time}")
            print(f"User's UTC time: {user_utc_time}")

            # If it's the correct time for the user and the update hasn't been sent yet, send the update
            if current_utc_time.hour == user_utc_time.hour and current_utc_time.minute == user_utc_time.minute:
                if user_id not in sent_updates:
                    location = user_data.get('location')

                    if location:
                        # Fetch weather data (assuming the API part is correct)
                        weather_api_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
                        response = requests.get(weather_api_url)
                        weather_data = response.json()

                        if response.status_code == 200:
                            main_weather = weather_data['weather'][0]['main']
                            description = weather_data['weather'][0]['description']
                            temperature = weather_data['main']['temp']
                            unit = user_data.get('unit', 'C')

                            if unit == 'F':
                                temperature = (temperature * 9/5) + 32

                            user = await bot.fetch_user(int(user_id))
                            if user:
                                print(f"User {user_id} found: {user}")
                                # Send DM to the user
                                try:
                                    channel = await user.create_dm()
                                    await channel.send(f'Daily weather update for {location}: {main_weather} ({description}) with a temperature of {temperature:.2f}°{"F" if unit == "F" else "C"}.')
                                    print(f"Sent update to user {user_id}")
                                    sent_updates.add(user_id)
                                except discord.Forbidden:
                                    print(f"Bot does not have permission to send DMs to user {user_id}")
                            else:
                                print(f"User {user_id} not found.")
                        else:
                            print(f"Unable to fetch daily weather update for {location}.")
                    else:
                        print(f"No location found for user {user_id}.")
        except Exception as e:
            print(f"Error processing updates for user {user_id}: {e}")

    # Clear the set of sent updates if the minute has changed
    if current_utc_time.minute != current_minute:
        sent_updates.clear()
      
# Event to print a message when the bot is ready
@bot.event
async def on_ready():
    send_daily_updates.start()
    await bot.tree.sync()
    print(f'{bot.user.name} has connected to Discord!')

@bot.event
async def on_disconnect():
    write_data(data)

# Run the bot
bot.run(DISCORD_TOKEN, reconnect=True)
# Event to print a message when the bot is ready
@bot.event
async def on_ready():
    send_daily_updates.start()
    await bot.tree.sync()
    print(f'{bot.user.name} has connected to Discord!')

@bot.event
async def on_disconnect():
    write_data(data)

# Run the bot
bot.run(DISCORD_TOKEN, reconnect=True)
