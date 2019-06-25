import time
from datetime import datetime
import logging.config
import json
import os
import argparse
import RPi.GPIO as GPIO

def setup_logging(default_path, default_level, env_key):
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)
        
logger = logging.getLogger(__name__)
setup_logging('/home/pi/pipower/pi_power_logging.json', logging.INFO, 'LOG_CFG')

# read SPI data from MCP3008 chip, 8 possible adc's (0 thru 7)
def readadc(adcnum, clockpin, mosipin, misopin, cspin):
        if ((adcnum > 7) or (adcnum < 0)):
                return -1
        GPIO.output(cspin, True)

        GPIO.output(clockpin, False)  # start clock low
        GPIO.output(cspin, False)     # bring CS low

        commandout = adcnum
        commandout |= 0x18  # start bit + single-ended bit
        commandout <<= 3    # we only need to send 5 bits here
        for i in range(5):
                if (commandout & 0x80):
                        GPIO.output(mosipin, True)
                else:
                        GPIO.output(mosipin, False)
                commandout <<= 1
                GPIO.output(clockpin, True)
                GPIO.output(clockpin, False)

        adcout = 0
        # read in one empty bit, one null bit and 10 ADC bits
        for i in range(12):
                GPIO.output(clockpin, True)
                GPIO.output(clockpin, False)
                adcout <<= 1
                if (GPIO.input(misopin)):
                        adcout |= 0x1

        GPIO.output(cspin, True)
        
        adcout >>= 1       # first bit is 'null' so drop it
        return adcout


# Calculate the output of a voltage divider
# voltage_divider layout is:
# Vin ---[ R1 ]---[ R2 ]---GND
#               |
#              Vout
#
# Vout = R2 / (R1 + R2) * Vin
# e.g. if R1 = 6800 and R2 = 10000 and Vin is 5.2V then Vout is 3.095
#
def voltage_divider(r1, r2, vin):
        vout = vin * (r2 / (r1 + r2))
        return vout



# Set up a trigger to shutdown the system when the power button is pressed
# define a setup routine and the actual shutdown method

# The shutdown code is based on that in https://github.com/NeonHorizon/lipopi

def user_shutdown_setup(shutdown_pin):
    # setup the pin to check the shutdown switch - use the internal pull down resistor
    GPIO.setup(shutdown_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # create a trigger for the shutdown switch
    GPIO.add_event_detect(shutdown_pin, GPIO.RISING, callback=user_shutdown, bouncetime=1000)

# User has pressed shutdown button - initiate a clean shutdown
def user_shutdown(channel):
    global safe_mode
    global user_shutdown_pin

    shutdown_delay = 5
    logger.info("user_shutdown()>Button pressed")
    pushTime = 0
    while pushTime < 3000:
        time.sleep(0.1)
        if GPIO.input(user_shutdown_pin) == 0:
            pushTime = 0
            logger.info("user_shutdown()>GPIO LOW")
            return            
        else: 
            pushTime = pushTime + 100 
            logger.info("user_shutdown()>GPIO HIGH")
        
    logger.info("user_shutdown()>Button has been pushed and held for 3000 ms")   
        
    logger.info("user_shutdown()>while loop ended") 
    # in Safe Mode, wait 2 mins before actually shutting down
    if(safe_mode):
        logger.info("user_shutdown()>System shutting down(user request) in 2 minutes - SAFE MODE")
        cmd = "sudo wall 'System shutting down(user request) in 2 minutes - SAFE MODE'"
        os.system(cmd)
        time.sleep(120)

    logger.info("user_shutdown()>System shutting down(user request) in %d seconds" % shutdown_delay)
    cmd = "sudo wall 'System shutting down(user request) in %d seconds'" % shutdown_delay
    os.system(cmd)
           
    # Log message is added to /var/log/messages
    os.system("sudo logger -t 'pi_power' '** User initiated shut down **'")
    GPIO.cleanup()
    os.system("sudo shutdown now")

# Shutdown system because of low battery
def low_battery_shutdown():
    global safe_mode

    shutdown_delay = 30 # seconds
    
    # in Safe Mode, wait 2 mins before actually shutting down
    if(safe_mode):            
        logger.info("low_battery_shutdown()> System shutting down(low battery) in 2 minutes - SAFE MODE")
        cmd = "sudo wall 'System shutting down(low battery) in 2 minutes - SAFE MODE'"
        os.system(cmd)
        time.sleep(120)
    
    logger.info("low_battery_shutdown()> System shutting down(low baterry) in %d seconds'" % shutdown_delay)
    cmd = "sudo wall 'System shutting down(low baterry) in %d seconds'" % shutdown_delay
    os.system(cmd)
    time.sleep(shutdown_delay)
    # Log message is added to /var/log/messages
    os.system("sudo logger -t 'pi_power' '** Low Battery - shutting down now **'")
    GPIO.cleanup()
    os.system("sudo shutdown now")
                

    

# MAIN -----------------------


GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Command Line Arguments
# --log    write time, voltage, etc to a log file
# --debug  write time, voltage, etc to STDOUT

parser = argparse.ArgumentParser(description='Pi Power - Monitor battery status on RasPi projects powered via Adafruit PowerBoost 1000C')

parser.add_argument('-s', '--safe',  action='store_true')

args = parser.parse_args()

safe_mode = False
if(args.safe):
        safe_mode = True

logger.info("main()> args= " + str(args)) 
logger.info("main()> safe mode>> low bat/user shutdown after 2 minutes")

# Setup the GPIO pin to use with the use shutdown button

user_shutdown_pin = 26
user_shutdown_setup(user_shutdown_pin)

# Setup the connection to the ADC

# specify the Raspberry Pi GPIO pins to be used to connect to the SPI interface on the MCP3008 ADC

SPICLK  = 17
SPIMISO = 23
SPIMOSI = 24
SPICS   = 25

# set up the SPI interface pins
GPIO.setup(SPIMOSI, GPIO.OUT)
GPIO.setup(SPIMISO, GPIO.IN)
GPIO.setup(SPICLK,  GPIO.OUT)
GPIO.setup(SPICS,   GPIO.OUT)

# Vbat to adc #0, Vusb connected to #1
v_bat_adc_pin = 0
v_usb_adc_pin = 1

# Voltage divider drops the PowerBoost voltage from around 5V to under 3.3V which is the limit for the Pi
voltage_divider_r1 =  6800.0
voltage_divider_r2 = 10000.0

# Define the min and max voltage ranges for the inputs
usb_min_voltage = 0.0
usb_max_voltage = 5.2

gpio_min_voltage = 0.0
gpio_max_voltage = 3.3

# LiPo battery voltage range - actual range is 3.7V to 4.2V
# But in practice the measured range is reduced as Vbat always drops from 4.2 to around 4.05 when the
# USB cable is removed - so this is the effective range:

battery_min_voltage = 3.75
battery_max_voltage = 4.05

# this is the effective max voltage, prior to the divider, that the ADC can register
adc_conversion_factor = (gpio_max_voltage / voltage_divider(voltage_divider_r1, voltage_divider_r2, usb_max_voltage)) * usb_max_voltage

# Take a measurement every poll_interval * seconds * - default 60
poll_interval = 10

power_source = ''
power_source_previous = ''

fraction_battery = 1.0

# Define the minimum battery level at which shutdown is triggered
fraction_battery_min = 0.075

elapsed_time = 0
msg = ''

#SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS LED state change  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS

# If you are using a common Anode RGB LED use these - most RGB Leds are this type
led_states = {'off': GPIO.HIGH, 'on': GPIO.LOW}

# If you are using a common Cathode configuration use this instead
#led_states = {'off': GPIO.LOW, 'on': GPIO.HIGH}


# Specify the RasPi GPIO pins to use - modufy these to suit your configuration
led_pin = {'red': 21, 'green': 8}

power_source = 'unknown'
power_fraction = 1.0

GPIO.setup(led_pin['red'],   GPIO.OUT)
GPIO.setup(led_pin['green'], GPIO.OUT)

# Define each LED mode - set the on/off times here (in seconds) - 0 means always on
def green_constant():
    blink_time_on  = 0
    blink_time_off = 0
    leds = ['green']
    #logger.info("green_constant()> leds= " + str(leds) + ", blink_time_on= " + str(blink_time_on) + ", blink_time_off= "+ str(blink_time_off))
    update_leds(leds, blink_time_on, blink_time_off)

def red_constant():        
        blink_time_on  = 0
        blink_time_off = 0
        leds = ['red']
        #logger.info("red_constant()> leds= " + str(leds) + ", blink_time_on= " + str(blink_time_on) + ", blink_time_off= "+ str(blink_time_off))
        update_leds(leds, blink_time_on, blink_time_off)

def yellow_constant():
        blink_time_on  = 0
        blink_time_off = 0
        leds = ['red', 'green']
        #logger.info("yellow_constant()> leds= " + str(leds) + ", blink_time_on= " + str(blink_time_on) + ", blink_time_off= "+ str(blink_time_off))
        update_leds(leds, blink_time_on, blink_time_off)

def green_blink():
        blink_time_on  = 2.0
        blink_time_off = 0.5
        leds = ['green']
        #logger.info("green_blink()> leds= " + str(leds) + ", blink_time_on= " + str(blink_time_on) + ", blink_time_off= "+ str(blink_time_off))
        update_leds(leds, blink_time_on, blink_time_off)

def red_blink():
        blink_time_on  = 1.0
        blink_time_off = 1.0
        leds = ['red']
        #logger.info("red_blink()> leds= " + str(leds) + ", blink_time_on= " + str(blink_time_on) + ", blink_time_off= "+ str(blink_time_off))
        update_leds(leds, blink_time_on, blink_time_off)

def red_blink_fast():
        blink_time_on  = 0.5
        blink_time_off = 0.5
        leds = ['red']
        #logger.info("red_blink_fast()> leds= " + str(leds) + ", blink_time_on= " + str(blink_time_on) + ", blink_time_off= "+ str(blink_time_off))
        update_leds(leds, blink_time_on, blink_time_off)

def update_leds(current_leds, time_on, time_off):
        global led_pin
        global led_states
        global poll_interval

        logger.info("update_leds()> current_leds= " + str(current_leds) + ", time_on= " + str(time_on) + ", time_off= "+ str(time_off))

        if time_off == 0:
                # constant on
                for i in range(len(current_leds)):
                        GPIO.output(led_pin[current_leds[i]], led_states['on'])
                time.sleep(poll_interval)
        else:
                # blink
                n_cycles = int(float(poll_interval) / float(time_on + time_off))
                logger.info("update_leds()> n_cycles = "+ str(n_cycles))
                for i in range(n_cycles):
                        # led on, sleep, led off, sleep
                        for i in range(len(current_leds)):
                                GPIO.output(led_pin[current_leds[i]], led_states['on'])
                        time.sleep(time_on)
                        for i in range(len(current_leds)):
                                GPIO.output(led_pin[current_leds[i]], led_states['off'])
                        time.sleep(time_off)
                

#EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE LED state change  EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE

try:
        while True:      
                # read the analog pins on the ACD (range 0-1023) and convert to 0.0-1.0
                frac_v_bat = round(readadc(v_bat_adc_pin,   SPICLK, SPIMOSI, SPIMISO, SPICS)) / 1023.0
                frac_v_usb = round(readadc(v_usb_adc_pin,   SPICLK, SPIMOSI, SPIMISO, SPICS)) / 1023.0
        
                # Calculate the true voltage
                v_bat = frac_v_bat * adc_conversion_factor
                v_usb = frac_v_usb * adc_conversion_factor
                        
                fraction_battery = (v_bat - battery_min_voltage) / (battery_max_voltage - battery_min_voltage)

                if fraction_battery > 1.0:
                        fraction_battery = 1.0
                elif fraction_battery < 0.0:
                        fraction_battery = 0.0
                
                # is the USB cable connected ? Vusb is either 0.0 or around 5.2V       
                if v_usb > 1.0:
                        power_source = 'usb'
                else:
                        power_source = 'battery'

                if power_source == 'usb' and power_source_previous == 'battery':
                        print '** USB cable connected'
                        logger.info("main()> ** USB cable connected")
                elif power_source == 'battery' and power_source_previous == 'usb':
                        print '** USB cable disconnected'
                        logger.info("main()> ** USB cable disconnected")

                power_source_previous = power_source

                logger.info("main()> elapsed_time= " + str(elapsed_time) + " , v_bat= " + str(v_bat) + " , v_usb= " + str(v_usb) + " , fraction_battery= " + str(fraction_battery) + " ,  power_source= " + str(power_source))

                # If battery is too low then shutdown
                if fraction_battery < fraction_battery_min:
                        print "** LOW BATTERY - shutting down........"
                        logger.info("main()> ** LOW BATTERY - shutting down........")
                        low_battery_shutdown()

                #SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS LED state change  SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS
                GPIO.output(led_pin['red'],   led_states['off'])
                GPIO.output(led_pin['green'], led_states['off'])

                if power_source == 'usb':
                        green_blink()
                elif power_source == 'battery':
                        if fraction_battery >= 0.50:
                                green_constant()
                        elif fraction_battery >= 0.25:
                                yellow_constant()
                        elif fraction_battery >= 0.15:
                                red_constant()
                        elif fraction_battery >= 0.10:
                                red_blink()
                        else:
                                red_blink_fast()
                else:
                        # Leave LEDs off - just sleep
                        time.sleep(poll_interval)
                #EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE LED state change  EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE

                elapsed_time += poll_interval
# End program cleanly with keyboard or sys.exit(0)
except KeyboardInterrupt:
        logger.info("Main()> Quit (Ctrl+C)")
except SystemExit:
        logger.info("Main()> Quit (SIGTERM)")
