"""
(C) MS Roth 2020-2023
Simple LED Clock with weather forecast and stock market update.

"""

import datetime
import time
from rgbmatrix import graphics, RGBMatrix, RGBMatrixOptions
import config
import sys
import argparse
import os
#import yfinance as yf
import multiprocessing as mp
import holidays
import requests
import urllib3
import urllib 
import dateutil.parser
from dateutil.tz import tzlocal
from timeloop import Timeloop
from samplebase import SampleBase


# disable HTTPS warnings
urllib3.disable_warnings()
        
# define time loop for weather, markets, and news updates
tl = Timeloop()

# global queues to pass strings among processes
qm = mp.Queue()
qw = mp.Queue()
qh = mp.Queue()


class Weather:
    """
    References:
    https://openweathermap.org/current
    """

    WEATHER_URL = 'http://api.openweathermap.org/data/2.5/weather?zip={},us&units=imperial&appid={}'
    FORECAST_URL = 'http://api.openweathermap.org/data/2.5/forecast?zip={},us&units=imperial&cnt=3&appid={}'
    ALERT_URL = 'http://api.weather.gov/alerts?active=true&point={},{}'
    weather_str = ''
    weather_api_key = ''
    weather_city = ''
        
    def __init__(self):
        self.weather_str = 'No Weather Data'
        self.weather_api_key = config.weather_api_key
        self.weather_city = config.weather_city       
        self.degrees = u"\N{Degree Sign}"
        self.headers = {'User-Agent': 'LED-Clock'}

    def get_weather(self, q):
        try:
            # get weather observations
            onset_time = None
            weather = requests.get(self.WEATHER_URL.format(self.weather_city, self.weather_api_key), headers=self.headers, verify=False).json()
            city = weather['name']
            coord = (weather['coord']['lat'], weather['coord']['lon'])
            temp_f = int(weather['main']['temp'])
            temp_c = int((temp_f - 32) / 1.8)
            feels_like = int(weather['main']['feels_like']/1.0)
            humidity = weather['main']['humidity']
            wind_dir = self.get_wind_direction(weather['wind']['deg'])
            wind_speed = int(weather['wind']['speed'])
            description = weather['weather'][0]['description']

            # get forcast
            forecast = requests.get(self.FORECAST_URL.format(self.weather_city, self.weather_api_key), headers=self.headers, verify=False).json()
            short_forecast = forecast['list'][2]['weather'][0]['description']
                      
            # get weather alerts
            alerts = requests.get(self.ALERT_URL.format(coord[0], coord[1]), headers=self.headers, verify=False).json()
            alert_str = ''
            if len(alerts['features']) > 0:
                onset_time = alerts['features'][len(alerts['features'])-1]['properties']['effective']  # take latest alert
                ends_time = alerts['features'][len(alerts['features'])-1]['properties']['ends']        # take latest alert 
                start_time = None
                end_time = None
                
                if onset_time is not None:
                    start_time = dateutil.parser.isoparse(onset_time)
                if ends_time is not None:
                    end_time = dateutil.parser.isoparse(ends_time)
                    
                # determine if statement is active
                if start_time is not None and end_time is not None:
                    now_time = datetime.datetime.now(tzlocal())
                    if start_time <= now_time < end_time:
                        alert_str = '! {} ! '.format(alerts['features'][len(alerts['features'])-1]['properties']['event'])  # take latest alert
                
                # sometimes there is no end date
                elif start_time is not None:
                    now_time = datetime.datetime.now(tzlocal())
                    if start_time <= now_time:
                        alert_str = '! {} ! '.format(alerts['features'][0]['properties']['event'])
                
            # build weather string with or without alert
            self.weather_str = '* Weather *  {} : {}{}{}f / {}{}c (feels like {}{}f). {}% rel hum.  winds {}@{}mph. {}. 3hr forecast: {}.'.format(city,
                                    alert_str, temp_f, self.degrees, temp_c, self.degrees, feels_like, self.degrees, humidity, wind_dir, wind_speed, description, short_forecast)

            #print('\nweather updated @ {}'.format(datetime.datetime.now()))
            print(self.weather_str)
            
            # put the weather string in the queue so it can be retrieved asynchronously.
            q.put(self.weather_str)
        except Exception as ex:
            print('Weather error: {}'.format(ex))
            q.put(self.weather_str)
        return
        
    def get_wind_direction(self, deg):
        """
        Return the compass directions for the wind
        """
        
        if 0 <= int(deg) <= 23 or 338 < int(deg) <= 360:
            return 'N'
        elif 23 < int(deg) <= 68:
            return 'NE'
        elif 68 < int(deg) <= 113:
            return 'E'
        elif 113 < int(deg) <= 158:
            return 'SE'
        elif 158 < int(deg) <= 203:
            return 'S'
        elif 203 < int(deg) <= 248:
            return 'SW'
        elif 248 < int(deg) <= 293:
            return 'W'
        else:
            return 'NW'
        
        
class Market:
    """
    Return stock market data from Yahoo Financial for the indexes in addition to other 
    symbols read from the config.py file.

    The ticker displays the current or last price and the delta from its opening price.

    """

    symbols = []
    market_str = ''
    MARKET_URL = 'http://query2.finance.yahoo.com/v8/finance/chart/{}'
    
    def __init__(self):
        self.market_str = 'No Market Data'
        self.symbols = ['^DJI', '^SPX']  # DJIA, S&P500
        self.symbols.extend(config.symbols)
        self.headers = {'User-Agent': 'LED-Clock'}
            
    def get_markets(self, q):
        try:
            
            if self.is_business_day() and self.is_business_hours():
                self.market_str = '* Market update *'
            else:
                self.market_str = '* Markets are closed *'
                            
            for symbol in self.symbols:   
                trend = ''
                url = self.MARKET_URL.format(urllib.parse.quote_plus(symbol))
                chart = requests.get(url, headers=self.headers, verify=False).json()
                
                close_price = float(chart['chart']['result'][0]['meta']['chartPreviousClose'])
                current_price = float(chart['chart']['result'][0]['meta']['regularMarketPrice'])
                dif = current_price - close_price

                if dif <= 0:
                    trend = '{:.2f}'.format(dif)
                else:
                    trend = '+{:.2f}'.format(dif)
                self.market_str += '  {}: {:.2f}/{}'.format(symbol, current_price, trend)
            print(self.market_str)
            
            # put the market string into the queue to be read later
            q.put(self.market_str)
        except Exception as ex:
            print('Markets error: {}'.format(ex))
            q.put(self.market_str)
        return

    def is_business_day(self):
        # is today Mon - Fri and not a US holiday
        now = datetime.datetime.now()
        today = datetime.date(now.year, now.month, now.day)
        if today in holidays.US():
            return False
        elif today.weekday() < 5:
            return True
        else:
            return False

    def is_business_hours(self):
        # US markets open at 0930 and close at 1600
        now = datetime.datetime.now()
        if now.hour == 9:
            if now.minute >= 30:
                return True
            else:
                return False
        elif (now.hour > 9 and now.hour < 16):
            return True
        else:
            return False
    

class Headlines:
    """
    Get top headlines (5) from source defined in config file
    """

    NEWS_URL = 'http://newsapi.org/v2/top-headlines?sources={}&apiKey={}'.format(config.news_source, config.news_api_key)
        
    def __init__(self):
        self.headline_str = 'No Headlines Data'
        self.headers = {'User-Agent': 'LED-Clock'}
        
    def get_headlines(self, q):
        
        try:
            response = requests.get(self.NEWS_URL, headers=self.headers, verify=False)
            top_headlines = response.json()

            self.headline_str = '* Headlines *  '
            headline = ''
            if int(top_headlines['totalResults']) >= 5:
                for i in range(5):
                    headline = top_headlines['articles'][i]['title']
                    self.headline_str += '{}.  '.format(headline)

            print(self.headline_str)
            
            # put the headlines string into the queue to be read later
            q.put(self.headline_str.rstrip())
        except Exception as ex:
            print('Headlines error: {}'.format(ex))
            q.put(self.headline_str)
        return


class Clock(SampleBase):
    def __init__(self, *args, **kwargs):
        super(Clock, self).__init__(*args, **kwargs)

    def run(self):
        """
        Run the clock.
        """
    
        # setup canvas
        canvas = self.matrix.CreateFrameCanvas()
        
        # fill it with black
        canvas.Fill(0, 0, 0)
        
        # setup the fonts for the clock
        font = graphics.Font()
        font.LoadFont("/home/pi/mlb-led-scoreboard/submodules/matrix/fonts/5x7.bdf")
        time_font = graphics.Font()
        time_font.LoadFont("/home/pi/mlb-led-scoreboard/submodules/matrix/fonts/7x13.bdf")
        
        # text will be yellow
        textColor = graphics.Color(255, 235, 59)

        # set initial values
        weather_string = 'No weather data yet.'
        market_string = 'No market data yet.'
        headlines_string = 'No headlines data yet.'
        
        big_x = 64
        last_switch = datetime.datetime.now().astimezone()
        show_dow = False
        init = True
        
        # start async jobs to update data
        tl.start(block=False)

        try:
            while True:
                
                # get the current time
                now = datetime.datetime.now().astimezone()

                # references for time formats
                # https://www.programiz.com/python-programming/datetime/strftime
                
                # if new weather data, use it
                if not qw.empty():
                    weather_string = qw.get()
                    
                # if new market data, use it
                if not qm.empty():
                    market_string = qm.get()
                    
                # if new market data, use it
                if not qh.empty():
                    headlines_string = qh.get()
                    
                # switch dow and date every X sec
                if (now - last_switch).seconds > config.face_flip_rate:
                    last_switch = datetime.datetime.now().astimezone()
                    if show_dow == False:
                        show_dow = True
                    else:
                        show_dow = False
                        
                # display clock    
                if show_dow == False:
                    #now = datetime.datetime.now()  # so seconds tick
                    date_string = now.strftime('%A')
                    time_string = now.strftime('%-I:%M %p')
                else:
                    date_string = now.strftime('%b %d, %Y')
                    time_string = now.strftime('%H:%M:%S')
                    
                # concat the msg strings
                msg_string = weather_string + ' '*8 + market_string + ' '*8 + headlines_string
                
                # fill convas with black
                canvas.Fill(0, 0, 0)
                
                # calculate element positions
                time_pos = int((64 - len(time_string) * 7) / 2)
                date_pos = int((64 - len(date_string) * 5) / 2)
                
                # put elements on canvas
                graphics.DrawText(canvas, time_font, time_pos, 11, textColor, time_string)
                graphics.DrawText(canvas, font, date_pos, 20, textColor, date_string)
                if init:
                    graphics.DrawText(canvas, font, 2, 30, textColor, 'Loading data')
                else:
                    graphics.DrawText(canvas, font, big_x, 30, textColor, msg_string)

                # calculate scroll horizontal position
                big_x = big_x - 1
                if big_x < len(msg_string) * -5:
                    big_x = 64
                
                # display the clock
                canvas = self.matrix.SwapOnVSync(canvas)
                
                # so you can read the scrolling message
                time.sleep(.06)

                if init:
                    update_weather()
                    update_markets()
                    update_headlines()
                    init = False
                    
        except KeyboardInterrupt:
            print("Exiting\n")
            tl.stop()
            sys.exit(0)


@tl.job(interval=datetime.timedelta(minutes=config.weather_update_rate))        
def update_weather():
    print('\nweather updated @ {}'.format(datetime.datetime.now().astimezone()))
    w = Weather()
    w.get_weather(qw)


@tl.job(interval=datetime.timedelta(minutes=config.market_update_rate))        
def update_markets():
    print('\nmarkets updated @ {}'.format(datetime.datetime.now().astimezone()))
    m = Market()
    m.get_markets(qm)


@tl.job(interval=datetime.timedelta(minutes=config.news_update_rate))        
def update_headlines():
    print('\nheadlines updated @ {}'.format(datetime.datetime.now().astimezone()))
    h = Headlines()
    h.get_headlines(qh)    


if __name__ == '__main__':
    print('(C) 2020-2023 MSRoth')
    print('LED clock on 64x32 LED matrix with weather, market, and news updates.')
    print('See config.py for details. Press CTRL-C to stop clock.')
    print('Loading data...\n\n')
    
    clock = Clock()
    if (not clock.process()):
        clock.print_help()
        tl.stop()

#<SDG><
