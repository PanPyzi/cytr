import os
import RPi.GPIO as GPIO
import pigpio
import time

screen_pin=12
screen_bttn_1=16
screen_bttn_2=18
screen_val=0
brightness_1=140
brightness_2=200
brightness_3=255
brt_val1=0
brt_val2=0
pi = pigpio.pi()

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

GPIO.setup(screen_bttn_1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(screen_bttn_2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

time.sleep(3)

def screen_brightness_2(x):
    global brt_val2, pi
    if brt_val2==0:
        brt_val2=1
        pi.set_PWM_dutycycle(12,0)
    else:
        brt_val2=0
        pi.set_PWM_dutycycle(12, 170)
    #print("Up+"+str(brt_val2))

def screen_brightness_1(x):
    global brt_val1, pi
    if brt_val1==0:
        brt_val1=1
        pi.set_PWM_dutycycle(12, 220)
    else:
        brt_val1=0
        pi.set_PWM_dutycycle(12, 170)
    #print("Down+"+str(brt_val1))

#GPIO.add_event_detect(screen_bttn_1,GPIO.RISING,callback=screen_brightness_1,bouncetime=500)
GPIO.add_event_detect(screen_bttn_1,GPIO.FALLING,callback=screen_brightness_1,bouncetime=500)
#GPIO.add_event_detect(screen_bttn_2,GPIO.RISING,callback=screen_brightness_2,bouncetime=500)
GPIO.add_event_detect(screen_bttn_2,GPIO.FALLING,callback=screen_brightness_2,bouncetime=500)

def main():
    while(True):
        pass

main()
