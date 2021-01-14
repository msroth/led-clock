#  !/usr/bin/env python
"""
(C) MS Roth 2021
Simple LED Clock with weather forecast and stock market update.

Python 2.7
"""

import datetime
import time
import pyowm
from rgbmatrix import graphics, RGBMatrix, RGBMatrixOptions
import config
import sys
import argparse
import os
   

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
    last_switch = datetime.datetime.now()
    show_dow = False
    
    while True:
        
        # get the current time
        now = datetime.datetime.now()
        
        # switch dow and date every X sec
        if (now - last_switch).seconds > 5:
            last_switch = datetime.datetime.now()
            if show_dow == True:
                show_dow = False
            else:
                show_dow = True
            
        # display clock    
        if show_dow == False:
            now = datetime.datetime.now()  # so seconds tick
            date_string = now.strftime('%A')
            time_string = now.strftime('%-I:%M %p')
        else:
            date_string = now.strftime('%b %d, %Y')
            time_string = now.strftime('%H:%M:%S')
            
        # fill convas with black
        canvas.Fill(0, 0, 0)
        
        # calculate element positions
        time_pos_x = int((64 - len(time_string) * 7) / 2)
        date_pos_x = int((64 - len(date_string) * 5) / 2)
        
        # put elements on canvas
        graphics.DrawText(canvas, time_font, time_pos_x, 16, textColor, time_string)
        graphics.DrawText(canvas, font, date_pos_x, 25, textColor, date_string)
        
        # display the clock
        canvas = matrix.SwapOnVSync(canvas)
        

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
        print('LED clock on 64x32 LED matrix')
        
        run(matrix)
    except KeyboardInterrupt:
        print("Exiting\n")
        sys.exit(0)


if __name__ == '__main__':
    main()

#<SDG><
