#!/usr/bin/python3
"""This example is for Raspberry Pi (Linux) only!
   It will not work on microcontrollers running CircuitPython!"""
#----------------------------------------------
# Enter camera Field Of View here (in degrees):
camFOV = 45
#----------------------------------------------

import os
import math
import time, datetime
import logging
import subprocess

import busio
import board

import numpy as np
import pygame
import pygame.camera
from pygame.locals import *

from scipy.interpolate import griddata
from colour import Color

import adafruit_amg88xx
# initialize display environment
try:
    os.putenv('SDL_FBDEV', '/dev/fb1')
    os.putenv('SDL_VIDEODRIVER', 'fbcon')
    os.putenv('SDL_MOUSEDRV', 'TSLIB')
    os.putenv('SDL_MOUSEDEV', '/dev/input/touchscreen')
    os.putenv('SDL_AUDIODRIVER', 'dummy')
    pygame.display.init()
    pygame.mouse.set_visible(False)

except:
    pygame.quit()
    os.unsetenv('SDL_FBDEV')
    os.unsetenv('SDL_VIDEODRIVER')
    os.unsetenv('SDL_MOUSEDRV')
    os.unsetenv('SDL_MOUSEDEV')
    pygame.display.init()
    pygame.display.set_caption('ThermalCamera')

pygame.init()

font = pygame.font.SysFont("comicsansms", 36)

height = 480
width  = 320

# FULL SCREEN COLORS
WHITE = (255,255,255)
BLACK = (0,0,0)
BLUE  = (0,0,255)
YELLOW= (255,255,0)
CYAN  = (0,255,255)
RED   = (255,0,0)
GRAY  = (128,128,128)

#low range of the sensor (this will be blue on the screen)
#MINTEMP = 16.

#high range of the sensor (this will be red on the screen)
#MAXTEMP = 32.

#how many color values we can have
COLORDEPTH = 1024


#initialize the sensor
i2c_bus = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_amg88xx.AMG88XX(i2c_bus)

# pylint: disable=invalid-slice-index
points = [(math.floor(ix / 8), (ix % 8)) for ix in range(0, 64)]
grid_x, grid_y = np.mgrid[0:7:32j, 0:7:32j]
# pylint: enable=invalid-slice-index


#the list of colors we can choose from
blue = Color("indigo")
colors = list(blue.range_to(Color("red"), COLORDEPTH))

#create the array of colors
colors = [(int(c.red * 255), int(c.green * 255), int(c.blue * 255)) for c in colors]

displayPixelWidth = width / 32
displayPixelHeight = height / 48 

# initialize camera
pygame.camera.init()
cam = pygame.camera.Camera("/dev/video0",(width, height))
cam.start()


# create surfaces
# display surface
lcd = pygame.display.set_mode()
#lcd = pygame.display.set_mode((width,height))
lcdRect = lcd.get_rect()
#print(lcdRect)

# heat surface
heat = pygame.surface.Surface((width, height))

# edge detect surface
overlay = pygame.surface.Surface((width, height))
overlay.set_colorkey((0,0,0))

# menu surface
menu = pygame.surface.Surface((width, height))
menu.set_colorkey((0,0,0))

# text surface
data = pygame.surface.Surface((width, height))
data.set_colorkey((0,0,0))

#lcd = pygame.display.set_mode((width, height))

lcd.fill((255, 0, 0))

pygame.display.update()
pygame.mouse.set_visible(False)

lcd.fill((0, 0, 0))
pygame.display.update()

#some utility functions
def constrain(val, min_val, max_val):
    return min(max_val, max(min_val, val))

def map_value(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def menuButton( menuText, menuCenter, menuSize ) :
    mbSurf = font.render(menuText,True,WHITE)
    mbRect = mbSurf.get_rect(center=menuCenter)
    menu.blit(mbSurf,mbRect)

    mbRect.size = menuSize
    mbRect.center = menuCenter
    pygame.draw.rect(menu,WHITE,mbRect,3)

    return mbRect

def textOverlay( text_words, posCenter, color=GRAY ) :
    toSurf = font.render(text_words,True,color)
    toSurf.fill((0,0,0))
    toSurf = font.render(text_words,True,color)
    toRect = toSurf.get_rect(center=posCenter)
    data.blit(toSurf,toRect)

    toRect.center = posCenter
    #pygame.draw.rect(data,RED,toRect,3)

    return toRect

# menu buttons and text

menuMode    = menuButton('Mode',   (160,120),(120,50) )
menuBack    = menuButton('Back',   (160,170),(120,50) )
menuCapture = menuButton('Capture',(160,270),(120,50) )

menuHalt    = menuButton('Halt',   (60,420),(100,50) )
menuReboot  = menuButton('Reboot', (160,420),(100,50) )
menuExit    = menuButton('Exit',   (260,420),(100,50) )

MAXtext = font.render('MAX', True, WHITE)
MAXtextPos = MAXtext.get_rect(center=(290,20))

MINtext = font.render('MIN', True, WHITE)
MINtextPos = MINtext.get_rect(center=(290,140))

# flags
menuDisplay = False 
# heatDisplay == 0	heat only
# heatDisplay == 1	heat + camera
# heatDisplay == 2	heat + +data + camera
# heatDisplay == 3	heat + data
heatDisplay = 2

imageCapture = False
systemHalt = False
systemReboot = False

# Field of View and Scale
heatFOV = 55
imageScale = math.tan(math.radians(camFOV/2.))/math.tan(math.radians(heatFOV/2.))

#let the sensor initialize
time.sleep(.1)

# initial low range of the sensor (this will be blue on the screen)
MINTEMP = 26
#MINTEMP = (73 - 32) / 1.8

# initial high range of the sensor (this will be red on the screen)
MAXTEMP = 32
#MAXTEMP = (79 - 32) / 1.8



#time.sleep(5)
host_ip = subprocess.getoutput("hostname -I")
#print(host_ip)

running=True
loopcount=0

start_time = time.time()
fr_string = ""

while (running):

    data.fill((0, 0, 0))
    # scan events
    for event in pygame.event.get():
        if (event.type is MOUSEBUTTONUP):
            if menuDisplay :
                pos = pygame.mouse.get_pos()

                if menuBack.collidepoint(pos):
                        menuDisplay = False
                if menuExit.collidepoint(pos):
                        running = False
                        print("program end")
                if menuHalt.collidepoint(pos):
                        systemHalt = True
                        running = False
                        print("system Halted")
                if menuReboot.collidepoint(pos):
                        systemReboot = True
                        running = False
                        print("system Rebooted")
                if menuMode.collidepoint(pos):
                        heatDisplay+=1
                        if heatDisplay > 3 :
                            heatDisplay = 0
                if menuCapture.collidepoint(pos):
                        imageCapture = not imageCapture

            else :
                menuDisplay = True

        if (event.type == KEYUP) :
            if (event.key == K_ESCAPE) :
                running = False

    #start_time = time.time()
    loopcount=loopcount+1

    #read the pixels
    spxls = sensor.pixels
    temp=sensor.temperature   

    tFile = open('/sys/class/thermal/thermal_zone0/temp')
    cputemp = float(tFile.read())
    cputempC = cputemp/1000
    
    #for row in spxls:
        # Pad to 1 decimal place
    #    print(['{0:.1f}'.format(temp) for temp in row])
    #    print("")
    #print("\n")

    flipv=np.fliplr(spxls)

    rot90=np.rot90(flipv,3)

    pixels_o = np.reshape(rot90,(8,8))

    pixels_d = np.reshape(rot90,(64))

    mintemp = min(pixels_d)
    maxtemp = max(pixels_d)
    
    pixels_d = [map_value(p, mintemp, maxtemp, 0, COLORDEPTH - 1) for p in pixels_d]

    #perform interpolation
    bicubic = griddata(points, pixels_d, (grid_x, grid_y), method='cubic')
    
    #draw everything
     
    for ix, row in enumerate(bicubic):
        for jx, pixel in enumerate(row):
            pygame.draw.rect(heat, colors[constrain(int(pixel),0,COLORDEPTH-1)],
                        (displayPixelHeight * ix, displayPixelWidth * jx + 80,
                         displayPixelHeight, displayPixelWidth))
     
    # show temperature of specific sensor
    rows=[0,1,2,3,4,5,6,7]
    cols=[0,1,2,3,4,5,6,7]
    # rows run horizontally <--->
    # columns run vertically 
    # ^
    # |
    # |
    
    for r in rows:
        for c in cols:
            text = font.render('{0:.0f}'.format(pixels_o[c][r]), True, GRAY)
            #text = pygame.transform.flip(text,True,False)
            #text = pygame.transform.rotate(text,-90)
            
            #pygame.draw.rect(lcd, colors[constrain(int(pixels[r+c*8]),0,COLORDEPTH-1)],
            #            (displayPixelWidth * 4*c, displayPixelHeight * 4*r + 80,
            #             displayPixelWidth*4, displayPixelHeight*4))
            
            data.blit(text,
                ( displayPixelWidth*4*c+5 , displayPixelHeight*4*r+8 +80 ))

            pygame.draw.rect(data, BLUE,
                    (displayPixelWidth *4*c, displayPixelHeight * 4*r +80,
                     displayPixelWidth*4, displayPixelHeight*4),1)
    
    # Flip the screen horizontally to match front facing IP camera
    #surf = pygame.transform.flip(lcd,True,False)
    #lcd.blit(surf,(0,0))

    #surf = pygame.transform.rotate(lcd,-90)
    #lcd.blit(surf,(-160,80))
    #pygame.display.flip()

    # Add Text to screen
    
    a_string = datetime.datetime.now().strftime('%a,  %d %b,  %H : %M : %S %Z ') 
    #text_surface = font.render(words, True, GRAY)
    #text.blit(text_surface, (10,400))
    textOverlay(a_string,(160,420))

    a_string = "CPU: {0:.1f}\N{DEGREE SIGN}C".format(cputempC)
    textOverlay(a_string,(160,440))

    a_string = "IP: " + host_ip
    if  a_string != "IP: " : 
      textOverlay(a_string,(160,460))

    a_string = "Min: {0:.0f}\N{DEGREE SIGN}C".format(mintemp)
    #text_surface = font.render(words, True, 
    #   colors[0])
    #text.blit(text_surface, (10,20))
    textOverlay(a_string,(80,30),colors[0])

    a_string = "Max: {0:.0f}\N{DEGREE SIGN}C".format(maxtemp)
    #text_surface = font.render(words, True,
    #   colors[COLORDEPTH-1])
    #text.blit(text_surface, (180,20))
    textOverlay(a_string,(240,30),colors[COLORDEPTH-1])

    a_string = "Snsr: {0:.1f}\N{DEGREE SIGN}C".format(temp)
    #text_surface = font.render(words, True, BLUE) 
    #text.blit(text_surface, (10,50))
    textOverlay(a_string,(80,60))

    #text = "IP : " + host_ip
    #text_surface = font.render(text, True, GRAY)
    #lcd.blit(text_surface, (50,450))

    # capture single frame to file, without menu overlay
    if imageCapture :
        imageCapture = False
        fileDate = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        fileName = "/home/pi/Pictures/heat%s.jpg" % fileDate
        print("picture " + fileName + " saved")
        pygame.image.save(heat, fileName)
    
    if loopcount > 10:
        #loop=0
        end_time = time.time()
        rate = 10/( end_time - start_time)
        #print("{0:.1f} frames/sec ".format(rate))

        fr_string = "{0:.1f} Frms/s".format(rate)
        #text_surface = font.render(a_string, True, BLUE)
        #data.blit(text_surface, (200,50))

        host_ip = subprocess.getoutput("hostname -I")
        loopcount = 0
        start_time = time.time()

    textOverlay(fr_string,(240,60))

    #camImage = pygame.transform.laplacian(cam.get_image())
    #pygame.transform.threshold(overlay,camImage,(0,0,0),(40,40,40),(1,1,1),1)

    camImage = cam.get_image()

    camRect = camImage.get_rect(center=lcdRect.center)
    camImage.set_alpha(100)


    lcd.blit(heat,(0,0))
    if heatDisplay == 1:
        lcd.blit(camImage,camRect)

    if heatDisplay == 2:
        lcd.blit(camImage,camRect)
        lcd.blit(data,(0,0))

    if heatDisplay == 3:
        lcd.blit(data,(0,0))

    # add menu overlay
    if menuDisplay :
        lcd.blit(menu,(0,0))


    pygame.display.flip()

#cam.stop()
pygame.quit()

if systemHalt:
    print("System Halt now")
    subprocess.getoutput("/home/pi/lcdoff")
    subprocess.getoutput("sudo shutdown -h -t 0")

if systemReboot:
    print("System Rebooting now")
    subprocess.getoutput("/home/pi/lcdoff")
    subprocess.getoutput("sudo shutdown -r -t 0")

