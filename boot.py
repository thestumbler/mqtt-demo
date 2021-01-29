# This file is executed on every boot (including wake-boot from deepsleep)
import time
from random import randint
import machine
from machine import Pin
import network
from umqtt.simple import MQTTClient
import esp
import webrepl
import dht
import neopixel

def reboot():
  machine.reset()

def webpython():
  webrepl.start()

def no_debug():
  esp.osdebug(None)

class wireless_network:
  def __init__(self):
    self.sta_if = None
  def connect(self, ssid, password):
    self.sta_if = network.WLAN(network.STA_IF)
    if not self.sta_if.isconnected():
      self.sta_if.active(True)
      self.sta_if.connect(ssid, password)
      while not self.sta_if.isconnected(): 
        pass
  def status(self):
    print('network config:', self.sta_if.ifconfig())
  def isconnected(self):
    return self.sta_if.isconnected()
   
class mqtt_client:
  def __init__(self, client_id, broker):
    self.client_id = client_id
    self.broker = broker
    self.mogi = MQTTClient(self.client_id, self.broker)
  def set_callback(self, callback):
    self.mogi.set_callback(callback)
  def connect(self):
    self.mogi.connect()
  def subscribe(self, topic):
    self.mogi.subscribe(topic)
  def publish(self, topic, value, retain=True):
    self.mogi.publish(topic, value, retain)
  def check_msg(self):
    self.mogi.check_msg()

class dht22_sensor:
  def __init__(self):
    self.dht22 = None
  def connect(self):
    self.dht22 = dht.DHT22(Pin(4))
  def measure(self):
    self.dht22.measure()
    self.temp = self.dht22.temperature()
    self.humid = self.dht22.humidity()
    return self.temp, self.humid

def clamp( val, lo, hi ):
  return min( hi, max( lo, val ) )

def clamp8( val ):
  return clamp( val, 0, 255 )

class led_strip:
  def __init__(self):
    self.pix = None
  def connect(self, num=8):
    self.pix = neopixel.NeoPixel(Pin(16,Pin.OUT),num)
  def all(self, color=(0xff,0xff,0xff)):
    for pixid in range(0,self.pix.n):
      self.pix[pixid]=color
    self.pix.write()
    time.sleep(0.150)
  def off(self):
    self.all((0,0,0))
  def random(self, nloop=100, dtime=0.100):
    for loop in range(0,nloop):
      pixid = randint(0,self.pix.n-1) 
      red = randint(0, randint(32, 128))
      green = randint(0, randint(32, 128))
      blue = randint(0, randint(32, 128))
      # Assign the current LED a random red, green and blue value between 0 and 
      self.pix[pixid] = (red, green, blue)
      # Display the current pixel data on the Neopixel strip
      self.pix.write()
      time.sleep(dtime)
    self.off()
  # led 0 = WiFi Connected
  def wifi(self,status):
    if status:
      self.pix[0] = (0,64,0)
    else:
      self.pix[0] = (64,0,0)
    self.pix.write()
    time.sleep(0.100)
  def temperature(self,data):
    r = int(  min(2*max(data-20, 0), 40)  )
    b = int(  max(40-2*data, 0)           )
    g = int(  20 - min(abs(20-data), 20)  )
    self.pix[7] = (clamp8(r),clamp8(g),clamp8(b))
    self.pix.write()
    time.sleep(0.100)
  def humidity(self,data):
    # same as above, just changed the rgb
    g = int(  min(2*max(data-20, 0), 40)  )
    r = int(  max(40-2*data, 0)           )
    b = int(  20 - min(abs(20-data), 20)  )
    self.pix[5] = (clamp8(r),clamp8(g),clamp8(b))
    self.pix.write()
    time.sleep(0.100)
  def whackme(self,data):
    print(data)
    if data is 'on':
      self.pix[2] = (0xff, 0xff, 0xff)
    else:
      self.pix[2] = (0,0,0)
    self.pix.write()
    time.sleep(0.100)

# subscribed message class for LED
class whackme_topic:
  def __init__(self):
    self.msg = 'nomessage'
    self.changed = False
  def callback(self,topic,msg):
    print( topic, msg )
    self.msg = msg.decode('utf-8')
    self.changed = True


MOGI_ID = 'esp32a-mogi'
MOGI_BROKER = 'underdog.lan'
WIFI_SSID = 'Covid-19-Laboratory'
WIFI_PASSWORD = 'yourpasswordhere'

def mystation(password=WIFI_PASSWORD):

  disp = led_strip()
  disp.connect()
  disp.off()
  print('connected to display.')
  disp.wifi(False)

  print('connecting to network...')
  wifi = wireless_network()
  wifi.connect(WIFI_SSID, password)
  wifi.status()
  disp.wifi(wifi.isconnected())

  whackme = whackme_topic()
  mogi = mqtt_client(MOGI_ID, MOGI_BROKER)
  mogi.set_callback(whackme.callback)
  mogi.connect()
  mogi.subscribe('test/whackme')
  print('connected to mqtt client.')

  sensor = dht22_sensor()
  sensor.connect()
  print('connected to sensor.')

  # loop executes once a second
  # but sensor reading only taken every INTERVAL seconds
  # (this is for timely response of subscribed topics)
  interval = 15
  sensor_timer = interval
  while True:
    if sensor_timer == interval:
      sensor_timer = 0
      # read sensor
      temp, humid = sensor.measure()
      # display locally
      disp.wifi(wifi.isconnected())
      disp.temperature(temp)
      disp.humidity(humid)
      print(temp, humid)
      # publish
      mogi.publish('test/temperature', str(temp) )
      mogi.publish('test/humidity', str(humid) )

    # check subscriptions
    sensor_timer += 1
    if whackme.changed:
      whackme.changed = False
      disp.whackme(whackme.msg)
    mogi.check_msg()
    time.sleep(1)

