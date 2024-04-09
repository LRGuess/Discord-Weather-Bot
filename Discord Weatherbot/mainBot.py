"""
Copyright (c) 2023 K-Bean Studios

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

You may not distribute or modify this script without proper credit to K-Bean Studios.
"""
import discord
from discord import app_commands
from discord.ext import tasks
import pytz
import requests
import datetime
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENWEATHERMAP_API_KEY = os.getenv('OPENWEATHERMAP_API_KEY')


# Create an instance of Intents
intents = discord.Intents.default()

# Create an instance of the bot
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Dictionary to store user default locations (user_id: location)
default_locations = {}

# Dictionary to store user default temperature units (user_id: unit)
default_units = {}

# Dictionary to store user daily update times (user_id: time)
daily_update_times = {}

# Dictionary to store format preferences for each user
format_preferences = {}

#Function to convert to local time
def convert_to_local_time(timestamp, timezone):
    utc_time = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    local_time = utc_time.astimezone(pytz.timezone(timezone))
    return local_time.strftime('%Y-%m-%d %H:%M:%S')


# Command to get the weather
@tree.command(name="weather", description="Get the current weather for a location")
async def get_weather(ctx: discord.Interaction, *, location: str = None):
    # Acknowledge the interaction
    await ctx.response.defer()

    # Retrieve user ID from the interaction
    user_id = ctx.user.id
    
    # Retrieve user preferences from the storage mechanism based on the user ID
    default_location = default_locations.get(user_id)
    default_unit = default_units.get(user_id, 'C')
    format_preference = format_preferences.get(user_id, 'embed')  # Get format preference or default to 'embed'

    if location is None:
        location = default_location
    
    if location is None:
        # Send a message to request a location
        await ctx.followup.send("Please provide a location or set a default location using /setlocation.")
        return

    # Call OpenWeatherMap API
    weather_api_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
    response = requests.get(weather_api_url)
    weather_data = response.json()

    # Check if the API request was successful
    if response.status_code == 200:
        # Extract relevant weather information
        main_weather = weather_data['weather'][0]['main']
        description = weather_data['weather'][0]['description']
        temperature_main = weather_data['main']['temp']

        temperature = temperature_main - 273.15

        # Convert temperature to the user's preferred unit
        if default_unit == 'F':
            temperature = (temperature_main - 273.15) * 9/5 + 32

        if format_preference.lower() == 'plain':
            # Send the weather information as plain text
            await ctx.followup.send(f'The weather in {location} is {main_weather} ({description}) with a temperature of {temperature:.2f}°{"F" if default_unit == "F" else "C"}.')
        else:
            # Send the weather information as an embed
            embed = discord.Embed(title=f"Weather in {location}", description=f"{main_weather} ({description}) with a temperature of {temperature:.2f}°{'F' if default_unit == 'F' else 'C'}")
            await ctx.followup.send(embed=embed)
    else:
        await ctx.followup.send(f"Unable to fetch weather data for {location}. Please check the location and try again.")

# Command to set a default location
@tree.command(name="setlocation", description="Set a default location for weather updates")
async def set_location(ctx: discord.Interaction, *, location: str):
    await ctx.response.defer()

    user_id = ctx.user.id
    default_locations[ctx.user.id] = location
    format_preference = format_preferences.get(user_id, 'embed')

    if format_preference.lower() == 'plain':
            # Send the weather information as plain text
            await ctx.followup.send(f'Default location set to {location}')
    else:
        # Send the weather information as an embed
        embed = discord.Embed(title=f"Setting location", description=f'Default location set to {location}')
        await ctx.followup.send(embed=embed)

# Command to set a default temperature unit
@tree.command(name="setunit", description="Set a default temperature unit (C or F)")
async def set_unit(ctx: discord.Interaction, unit: str):
    await ctx.response.defer()

    user_id = ctx.user.id
    format_preference = format_preferences.get(user_id, 'embed')
    unit = unit.upper()
    default_units[ctx.user.id] = unit

    if unit == 'C' or unit == 'F':
        if format_preference.lower() == 'plain':
            #send message as a plain text
            await ctx.followup.send(f'Default temperature unit set to {unit}.')
        else:
            #send as embed
            embed = discord.Embed(title=f'Unit set', description=f'Default temperature unit set to {unit}.')
            await ctx.followup.send(embed=embed)
    else:
        if format_preference.lower() == 'plain':
            #send message as a plain text
            await ctx.followup.send('Invalid unit. Please use C or F.')
        else:
            #send as embed
            embed = discord.Embed(title=f'Unit invalid', description='Invalid unit. Please use C or F.')
            await ctx.followup.send(embed=embed)

# Command to set a daily update time
@tree.command(name="dailyupdate", description="Set a specific time for daily weather updates")
async def set_daily_update(ctx: discord.Interaction, time: str):
    await ctx.response.defer()

    try:
        # Parse the time string and convert it to a datetime.time object
        update_time = datetime.datetime.strptime(time, '%H:%M').time()

        # Store the user's daily update time
        daily_update_times[ctx.user.id] = update_time

        await ctx.followup.send(f'Daily weather update time set to {time}.')
    except ValueError:
        await ctx.followup.send('Invalid time format. Please use HH:MM.')

# Command to get the wind information
@tree.command(name="wind", description="Get the wind information for a location")
async def get_wind(ctx: discord.Interaction, *, location: str = None):
    await ctx.response.defer()

    if location is None:
        # Check if user has a default location
        if ctx.user.id in default_locations:
            location = default_locations[ctx.user.id]
        else:
            await ctx.followup.send("Please provide a location or set a default location using /setlocation.")
            return

    # Call OpenWeatherMap API
    weather_api_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
    response = requests.get(weather_api_url)
    weather_data = response.json()

    # Check if the API request was successful
    if response.status_code == 200:
        # Extract wind information
        wind_speed = weather_data['wind']['speed']
        wind_direction = weather_data['wind']['deg']

        # Send the wind information to the Discord channel
        await ctx.followup.send(f'The wind in {location} is blowing at {wind_speed} m/s in the direction of {wind_direction}°.')
    else:
        await ctx.followup.send(f"Unable to fetch wind information for {location}. Please check the location and try again.")

# Command to get the humidity information
@tree.command(name="humidity", description="Get the humidity information for a location")
async def get_humidity(ctx: discord.Interaction, *, location: str = None):
    await ctx.response.defer()

    if location is None:
        # Check if user has a default location
        if ctx.user.id in default_locations:
            location = default_locations[ctx.user.id]
        else:
            await ctx.followup.send("Please provide a location or set a default location using /setlocation.")
            return

    # Call OpenWeatherMap API
    weather_api_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
    response = requests.get(weather_api_url)
    weather_data = response.json()

    # Check if the API request was successful
    if response.status_code == 200:
        # Extract humidity information
        humidity = weather_data['main']['humidity']

        # Send the humidity information to the Discord channel
        await ctx.followup.send(f'The humidity in {location} is {humidity}%.')
    else:
        await ctx.followup.send(f"Unable to fetch humidity information for {location}. Please check the location and try again.")

# Command to get the weather forecast
@tree.command(name="forecast", description="Get the weather forecast for a location")
async def get_forecast(ctx: discord.Interaction, *, location: str = None):
    await ctx.response.defer()

    if location is None:
        # Check if user has a default location
        if ctx.user.id in default_locations:
            location = default_locations[ctx.user.id]
        else:
            await ctx.followup.send("Please provide a location or set a default location using /setlocation.")
            return

    # Call OpenWeatherMap One Call API
    forecast_api_url = f'https://api.openweathermap.org/data/2.5/onecall?lat=0&lon=0&exclude=current,minutely,hourly,alerts&appid={OPENWEATHERMAP_API_KEY}&q={location}'
    response = requests.get(forecast_api_url)
    forecast_data = response.json()

    # Check if the API request was successful
    if response.status_code == 200:
        # Extract the daily forecast
        daily_forecast = forecast_data['daily']

        # Display the forecast for the next few days
        forecast_message = f'Weather forecast for {location}:\n'
        for day in daily_forecast:
            date = day['dt']
            temperature_min = day['temp']['min']
            temperature_max = day['temp']['max']
            description = day['weather'][0]['description']

            # Convert temperature to the user's preferred unit
            if ctx.user.id in default_units and default_units[ctx.user.id] == 'F':
                temperature_min = (temperature_min * 9/5) + 32
                temperature_max = (temperature_max * 9/5) + 32

            forecast_message += f'{date}: Min Temp: {temperature_min:.2f}°{"F" if ctx.user.id in default_units and default_units[ctx.user.id] == "F" else "C"}, Max Temp: {temperature_max:.2f}°{"F" if ctx.user.id in default_units and default_units[ctx.user.id] == "F" else "C"}, Weather: {description}\n'

        # Send the forecast information to the Discord channel
        await ctx.followup.send(forecast_message)
    else:
        await ctx.followup.send(f"Unable to fetch weather forecast for {location}. Please check the location and try again.")

# Command to get sunrise and sunset times
@tree.command(name="suntimes", description="Get sunrise and sunset times for a location")
async def get_sun_times(ctx: discord.Interaction, *, location: str = None):
    await ctx.response.defer()

    if location is None:
        # Check if user has a default location
        if ctx.user.id in default_locations:
            location = default_locations[ctx.user.id]
        else:
            await ctx.followup.send("Please provide a location or set a default location using /setlocation.")
            return

    # Call OpenWeatherMap API
    weather_api_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
    response = requests.get(weather_api_url)
    weather_data = response.json()

    # Check if the API request was successful
    if response.status_code == 200:
        # Extract sunrise and sunset times
        sunrise_timestamp = weather_data['sys']['sunrise']
        sunset_timestamp = weather_data['sys']['sunset']

        # Convert timestamps to timezone-aware datetime objects
        timezone_offset = weather_data['timezone']
        sunrise_time_utc = datetime.datetime.fromtimestamp(sunrise_timestamp, tz=pytz.utc)
        sunrise_time_local = sunrise_time_utc.astimezone(pytz.timezone(f'Etc/GMT{timezone_offset//3600}'))
        sunset_time_utc = datetime.datetime.fromtimestamp(sunset_timestamp, tz=pytz.utc)
        sunset_time_local = sunset_time_utc.astimezone(pytz.timezone(f'Etc/GMT{timezone_offset//3600}'))

        # Convert datetime objects to Unix timestamps
        sunrise_timestamp = sunrise_time_local.timestamp()
        sunset_timestamp = sunset_time_local.timestamp()

        # Format timestamps as Discord timestamps
        formatted_sunrise_time = f'<t:{int(sunrise_timestamp)}:R>'
        formatted_sunset_time = f'<t:{int(sunset_timestamp)}:R>'


        # Send the sunrise and sunset times with Discord timestamps to the Discord channel
        await ctx.followup.send(f'The sunrise in {location} is at {formatted_sunrise_time}, and the sunset is at {formatted_sunset_time}.')
    else:
        await ctx.followup.send(f"Unable to fetch sunrise and sunset times for {location}. Please check the location and try again.")

# Command to get weather alerts for a location
@tree.command(name="alerts", description="Get weather alerts for a location")
async def get_alerts(ctx: discord.Interaction, *, location: str = None):    
    await ctx.response.defer()

    if location is None:
        # Check if user has a default location
        if ctx.user.id in default_locations:
            location = default_locations[ctx.user.id]
        else:
            await ctx.followup.send("Please provide a location or set a default location using /setlocation.")
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
            
            await ctx.followup.send(alert_message)
        else:
            await ctx.followup.send(f'No weather alerts for {location}.')
    else:
        await ctx.followup.send(f"Unable to fetch weather alerts for {location}. Please check the location and try again.")
# Command to set message format preference
@tree.command(name="format", description="Choose message format (embed/plain)")
async def format_message(ctx: discord.Interaction, message_format: str):
    await ctx.response.defer()

    if message_format.lower() in ['embed', 'plain']:
        # Store the format preference for the user
        format_preferences[ctx.user.id] = message_format.lower()
        await ctx.followup.send(f'Message format preference set to {message_format.lower()}.')
    else:
        await ctx.followup.send('Invalid format. Please choose either "embed" or "plain".')


@tree.command(name="weatherbotabout", description="Get information about the weather bot")
async def info_command(ctx: discord.Interaction):
    await ctx.response.defer()

    # Provide a brief description of the bot
    description = "A cool bot that can tell you the weather, forecast, wind, and more! Website and full list of commands here: https://kbeanstudios.ca/discordweatherbot. You can also run /help"

    # Send the bot information to the Discord channel
    await ctx.followup.send(description)

@tree.command(name="weatherbothelp", description="Full list of commands")
async def help_command(ctx:discord.Interaction):
    await ctx.response.defer()
     
    commandlist = "/weather[location] provides weather for specified location \n /forecast[location] Retrieve a multi-day weather forecast for the specified location \n /setlocation[location] Set your default location for weather updates \n /setunit[F or C] Choose between Celsius and Fahrenheit for temperature units \n /dailyupdate[time] Receive a daily weather update at the specified time \n /wind[location] Get detailed information about the wind conditions at a specific location \n /humidity[location] Check the current humidity level for a given location \n /suntimes[location] Find out the sunrise and sunset times for a particular location \n /alerts[] Receive any weather alerts or warnings for the specified location \n /format[embed/plain] Choose between an embedded or plain text format for weather responses \n /weatherbotinfo[] Get information about WeatherBot, including version and support details"

    await ctx.followup.send(commandlist)

@tree.command(name="smiley", description="Send a smiley face haha")
async def smiley_command(ctx:discord.Interaction):
    await ctx.response.defer()

    await ctx.followup.send("😁")

@tasks.loop(hours=24)
async def send_daily_updates():
    current_time = datetime.datetime.now().time()

    for user_id, update_time in daily_update_times.items():
        if current_time.hour == update_time.hour and current_time.minute == update_time.minute:
            # Get the user's default location
            location = default_locations.get(user_id)

            if location:
                # Call OpenWeatherMap API
                weather_api_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHERMAP_API_KEY}'
                response = requests.get(weather_api_url)
                weather_data = response.json()

                # Check if the API request was successful
                if response.status_code == 200:
                    # Extract relevant weather information
                    main_weather = weather_data['weather'][0]['main']
                    description = weather_data['weather'][0]['description']
                    temperature = weather_data['main']['temp']

                    # Convert temperature to the user's preferred unit
                    unit = default_units.get(user_id, 'C')
                    if unit == 'F':
                        temperature = (temperature * 9/5) + 32

                    # Get the user's DM channel
                    user = client.get_user(user_id)
                    if user:
                        # Send the daily weather update
                        await user.send(f'Daily weather update for {location}: {main_weather} ({description}) with a temperature of {temperature:.2f}°{"F" if unit == "F" else "C"}.')
                else:
                    print(f"Unable to fetch daily weather update for {location}.")
                    # Log the error or handle it as needed

# Event to print a message when the bot is ready
@client.event
async def on_ready():
    send_daily_updates.start()
    await tree.sync()
    print(f'{client.user.name} has connected to Discord!')

# Run the bot
client.run(DISCORD_TOKEN, reconnect=True)
