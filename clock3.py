"""
(C) MS Roth 2021
Simple LED Clock with weather forecast and stock market update.

"""

import datetime
import time
from rgbmatrix import graphics, RGBMatrix, RGBMatrixOptions
import config
import sys
import argparse
import os
import yfinance as yf
import multiprocessing as mp
import holidays
import requests
import urllib3
import dateutil.parser
from dateutil.tz import tzlocal
from timeloop import Timeloop

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
        
    def get_weather(self, q):
        try:
            # get weather observations
            #print(self.WEATHER_URL.format(self.weather_city, self.weather_api_key))
            onset_time = None
            weather = requests.get(self.WEATHER_URL.format(self.weather_city, self.weather_api_key), verify=False).json()
            city = weather['name']
            coord = (weather['coord']['lat'], weather['coord']['lon'])
            temp_f = int(weather['main']['temp'])
            temp_c = int((temp_f - 32) / 1.8)
            humidity = weather['main']['humidity']
            wind_dir = self.get_wind_direction(weather['wind']['deg'])
            wind_speed = int(weather['wind']['speed'])
            description = weather['weather'][0]['description']
            self.weather_str = '* Weather *  {}: {}f / {}c  {}% hum  {}@{}mph {}'.format(city,
                                temp_f, temp_c, humidity, wind_dir, wind_speed, description)

            # get forcast
            # print(self.FORECAST_URL.format(self.weather_city, self.weather_api_key))
            forecast = requests.get(self.FORECAST_URL.format(self.weather_city, self.weather_api_key), verify=False).json()
            short_forecast = forecast['list'][2]['weather'][0]['description']
            self.weather_str += ' 3hr forecast: {}'.format(short_forecast)
            
            # get weather alerts
            # print(self.ALERT_URL.format(coord[0], coord[1]))
            alerts = requests.get(self.ALERT_URL.format(coord[0], coord[1]), verify=False).json()
            alert_str = ''
            if len(alerts['features']) > 0:
                #onset_time = alerts['features'][0]['properties']['onset']
                ends_time = alerts['features'][0]['properties']['ends']
                start_time = None
                end_time = None
                
                if onset_time is not None:
                    start_time = dateutil.parser.isoparse(onset_time)
                if ends_time is not None:
                    end_time = dateutil.parser.isoparse(ends_time)
                    
                # determine if statement is active
                if start_time is not None and end_time is not None:
                    now_time = datetime.datetime.now(tzlocal())
                    if start_time < now_time < end_time:
                        alert_str = '! {} !'.format(alerts['features'][0]['properties']['event'])
                
                # sometimes there is no end date
                elif start_time is not None:
                    now_time = datetime.datetime.now(tzlocal())
                    if start_time < now_time:
                        alert_str = '! {} !'.format(alerts['features'][0]['properties']['event'])
                
            # build weather string
            if len(alert_str) > 1:
                self.weather_str = '* Weather *  {}: {}  {}f / {}c  {}% hum  {}@{}mph  {}  3hr forecast: {}'.format(city,
                                    alert_str, temp_f, temp_c, humidity, wind_dir, wind_speed, description, short_forecast)
         
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
        Return the cardinal directions for the wind
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
    Return stock market data for the indexes in addition to other symbols read from
    the config.py file.

    While the market is open, the ticker displays the current ask price and the delta from its
    opening price.

    While the market is closed, it displays the last close price.
    """

    symbols = ['^DJI', '^SPX']  # DJIA, S&P500
    market_str = ''
    
    def __init__(self):
        self.market_str = 'No Market Data'
        self.symbols.extend(config.symbols)
        
    def get_markets(self, q):
        try:
            tickers = yf.Tickers(self.symbols)
            
            if self.is_business_day() and self.is_business_hours():
                self.market_str = '* Market update *'
                #for i in range(len(tickers.tickers)):
                for i in tickers.tickers:
                    trend = ''
                    avg_bid_ask = (float(tickers.tickers[i].info['bid']) + float(tickers.tickers[i].info['ask']))/2 
                    dif = avg_bid_ask - float(tickers.tickers[i].info['open'])
                    if dif <= 0:
                        trend = '{:.2f}'.format(dif)
                    else:
                        trend = '+{:.2f}'.format(dif)
                    self.market_str += '  {}: {:.2f}/{}'.format(tickers.tickers[i].info['symbol'],
                                                      avg_bid_ask, trend)
            else:
                self.market_str = '* Markets are closed *'
                #for i in range(len(tickers.tickers)):
                for i in tickers.tickers:
                    trend = ''
                    dif = float(tickers.tickers[i].history()['Close'][-1]) - float(tickers.tickers[i].info['previousClose']) 
                    if dif <= 0:
                        trend = '{:.2f}'.format(dif)
                    else:
                        trend = '+{:.2f}'.format(dif)
                    self.market_str += '  {}: {:.2f}/{}'.format(tickers.tickers[i].info['symbol'],
                                                      tickers.tickers[i].history()['Close'][-1],
                                                      trend)
                          
            #print('\nmarket updated @ {}'.format(datetime.datetime.now()))
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
    Get top headlines
    """

    headline_str = ''
    NEWS_URL = 'http://newsapi.org/v2/top-headlines?sources={}&apiKey={}'.format(config.news_source, config.news_api_key)
        
    def __init__(self):
        self.headline_str = 'No Headlines Data'
        
    def get_headlines(self, q):
        
        try:
            response = requests.get(self.NEWS_URL, verify=False)
            top_headlines = response.json()

            self.headline_str = '* Headlines *  '
            headline = ''
            if int(top_headlines['totalResults']) >= 5:
                for i in range(5):
                    headline = top_headlines['articles'][i]['title']
                    self.headline_str += '{};  '.format(headline.encode('ascii', 'ignore'))

            #print('\nheadlines updated @ {}'.format(datetime.datetime.now()))
            print(self.headline_str)
            
            # put the headlines string into the queue to be read later
            q.put(self.headline_str.rstrip())
        except Exception as ex:
            print('Headlines error: {}'.format(ex))
            q.put(self.headline_str)
        return


@tl.job(interval=datetime.timedelta(minutes=config.weather_update_rate))        
def update_weather():
    print('\nweather updated @ {}'.format(datetime.datetime.now()))
    w = Weather()
    w.get_weather(qw)


@tl.job(interval=datetime.timedelta(minutes=config.market_update_rate))        
def update_markets():
    print('\nmarkets updated @ {}'.format(datetime.datetime.now()))
    m = Market()
    m.get_markets(qm)


@tl.job(interval=datetime.timedelta(minutes=config.news_update_rate))        
def update_headlines():
    print('\nheadlines updated @ {}'.format(datetime.datetime.now()))
    h = Headlines()
    h.get_headlines(qh)    


def run(matrix):
    """
    Run the clock.
    """
    
    # setup canvas
    canvas = matrix.CreateFrameCanvas()
    
    # fill it with black
    canvas.Fill(0, 0, 0)
    
    # setup the fonts for the clock
    font = graphics.Font()
    font.LoadFont("../rpi-rgb-led-matrix/fonts/5x7.bdf")
    time_font = graphics.Font()
    time_font.LoadFont("../rpi-rgb-led-matrix/fonts/7x13.bdf")
    
    # text will be yellow
    textColor = graphics.Color(255, 235, 59)

    # set initial values
    weather_string = 'No weather data.'
    market_string = 'No market data.'
    headlines_string = 'No headlines data.'
    
    big_x = 64
    last_switch = datetime.datetime.now()
    show_dow = False
    init = True
    
    # start async jobs to update data
    tl.start(block=False)

    while True:
        
        # get the current time
        now = datetime.datetime.now()

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
            last_switch = datetime.datetime.now()
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
        msg_string = weather_string + ' '*12 + market_string + ' '*12 + headlines_string
        
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
        canvas = matrix.SwapOnVSync(canvas)
        
        # so you can read the scrolling message
        time.sleep(.06)

        if init:
            update_weather()
            update_markets()
            update_headlines()
            init = False
            

def main():
    """
    from samplebase.py
    """
    
    sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

    parser = argparse.ArgumentParser()
    
    parser.add_argument("-r", "--led-rows", action="store", help="Display rows. 16 for 16x32, 32 for 32x32. Default: 32", default=32, type=int)
    parser.add_argument("--led-cols", action="store", help="Panel columns. Typically 32 or 64. (Default: 32)", default=32, type=int)
    parser.add_argument("-c", "--led-chain", action="store", help="Daisy-chained boards. Default: 1.", default=1, type=int)
    parser.add_argument("-P", "--led-parallel", action="store", help="For Plus-models or RPi2: parallel chains. 1..3. Default: 1", default=1, type=int)
    parser.add_argument("-p", "--led-pwm-bits", action="store", help="Bits used for PWM. Something between 1..11. Default: 11", default=11, type=int)
    parser.add_argument("-b", "--led-brightness", action="store", help="Sets brightness level. Default: 100. Range: 1..100", default=100, type=int)
    parser.add_argument("-m", "--led-gpio-mapping", help="Hardware Mapping: regular, adafruit-hat, adafruit-hat-pwm" , choices=['regular', 'adafruit-hat', 'adafruit-hat-pwm'], type=str)
    parser.add_argument("--led-scan-mode", action="store", help="Progressive or interlaced scan. 0 Progressive, 1 Interlaced (default)", default=1, choices=range(2), type=int)
    parser.add_argument("--led-pwm-lsb-nanoseconds", action="store", help="Base time-unit for the on-time in the lowest significant bit in nanoseconds. Default: 130", default=130, type=int)
    parser.add_argument("--led-show-refresh", action="store_true", help="Shows the current refresh rate of the LED panel")
    parser.add_argument("--led-slowdown-gpio", action="store", help="Slow down writing to GPIO. Range: 1..100. Default: 1", choices=range(3), type=int)
    parser.add_argument("--led-no-hardware-pulse", action="store", help="Don't use hardware pin-pulse generation")
    parser.add_argument("--led-rgb-sequence", action="store", help="Switch if your matrix has led colors swapped. Default: RGB", default="RGB", type=str)
    parser.add_argument("--led-pixel-mapper", action="store", help="Apply pixel mappers. e.g \"Rotate:90\"", default="", type=str)
    parser.add_argument("--led-row-addr-type", action="store", help="0 = default; 1=AB-addressed panels;2=row direct", default=0, type=int, choices=[0,1,2])
    parser.add_argument("--led-multiplexing", action="store", help="Multiplexing type: 0=direct; 1=strip; 2=checker; 3=spiral; 4=ZStripe; 5=ZnMirrorZStripe; 6=coreman; 7=Kaler2Scan; 8=ZStripeUneven (Default: 0)", default=0, type=int)

    args = parser.parse_args()

    options = RGBMatrixOptions()

    if args.led_gpio_mapping != None:
        options.hardware_mapping = args.led_gpio_mapping
      
    options.rows = args.led_rows
    options.cols = args.led_cols
    options.chain_length = args.led_chain
    options.parallel = args.led_parallel
    options.row_address_type = args.led_row_addr_type
    options.multiplexing = args.led_multiplexing
    options.pwm_bits = args.led_pwm_bits
    options.brightness = args.led_brightness
    options.pwm_lsb_nanoseconds = args.led_pwm_lsb_nanoseconds
    options.led_rgb_sequence = args.led_rgb_sequence
    options.pixel_mapper_config = args.led_pixel_mapper
    
    if args.led_show_refresh:
        options.show_refresh_rate = 1

    if args.led_slowdown_gpio != None:
        options.gpio_slowdown = args.led_slowdown_gpio
        
    if args.led_no_hardware_pulse:
        options.disable_hardware_pulsing = True

    matrix = RGBMatrix(options = options)

    try:
        # Start loop
        print('(C) 2020-2021 MSRoth')
        print('LED clock on 64x32 LED matrix with weather, market, and news updates.')
        print('See config.py for details. Press CTRL-C to stop clock.')
        print('Loading data...\n\n')
        
        run(matrix)
    except KeyboardInterrupt:
        print("Exiting\n")
        tl.stop()
        sys.exit(0)


if __name__ == '__main__':
    main()

#<SDG><
