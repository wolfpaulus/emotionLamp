# emoLamp.py
# Author Wolf Paulus, Intuit IAT
# Version 2018-03-12

import os
import sys
import platform
import math
import copy
import time
import threading
import logging
import pyaudio
import wave
import scipy.io.wavfile
from pydub import AudioSegment
from magicblue import MagicBlue, Effect
import RPi.GPIO as GPIO
import apa102
import Vokaturi
import params

logging.basicConfig(filename='eli.log', level=logging.INFO, format='%(asctime)s %(message)s')
logging.info(platform.machine())  # Hardware 'pi3b.so' or 'piZero.so'

if platform.machine() == 'armv7l':
    Vokaturi.load('./lib/pi3b.so')
    logging.info('pi3b.so loaded')
else:
    Vokaturi.load('./lib/piZero.so')
    logging.info('piZero.so loaded')

WAVE_FILENAME = "sound.wav"
WORK_FILENAME = "work.wav"
NORM_WAV_FILENAME = "normalized.wav"
FORMAT = pyaudio.paInt16
CHUNK = 1024
CHANNELS = 1
RATE = 44100
TARGET_DBFS = -25
MAX_LOUDNESS = 103  # raw reading  would be -3


class MagicHue:
    def __init__(self, mac, version):
        self.mac = mac
        self.ver = version
        self.bulb = MagicBlue(self.mac, self.ver)
        self.bulb.connect()
        self.bulb.turn_off()  # Turn off the light
        self.bulb.turn_on(0.5)  # Set white light
        self.bulb.set_effect(Effect.cyan_gradual_change, 20)

    def set_color(self, rgb):
        if self.check():
            self.bulb.set_color(rgb)

    def check(self):
        if not self.bulb.test_connection():
            logging.warning('bulb not connected')
            set_neos([2, 0, 0], [0, 0, 0], [0, 0, 0])
            if not self.bulb.connect():
                self.bulb = MagicBlue(self.mac, self.ver)
                self.bulb.connect()
                return self.bulb.test_connection()
        return True


class RecordThread(threading.Thread):
    def __init__(self, thread_id, name, counter):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.name = name
        self.counter = counter

    def run(self):
        record(WAVE_FILENAME)


class AnalyzeThread(threading.Thread):
    def __init__(self, thread_id, name, counter):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.name = name
        self.counter = counter

    def run(self):
        try:
            if os.path.exists(WORK_FILENAME):
                normalized_sound(WORK_FILENAME, NORM_WAV_FILENAME)
                analyze(NORM_WAV_FILENAME)
        except (RuntimeError, TypeError, NameError):
            pass


def record(file_name):
    """Record from OS defined input source"""
    global sample_time
    frames = []
    for i in range(0, int(RATE / CHUNK * sample_time)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    wave_file = wave.open(file_name, 'wb')
    wave_file.setnchannels(CHANNELS)
    wave_file.setsampwidth(p.get_sample_size(FORMAT))
    wave_file.setframerate(RATE)
    wave_file.writeframes(b''.join(frames))
    wave_file.close()


def normalized_sound(source_file, target_file):
    """Normalizes the provided source_file into the target_file"""
    global decibel
    sound = AudioSegment.from_wav(source_file)
    decibel = sound.dBFS  # -3 is (maximum loudness)
    normalized = sound.apply_gain(TARGET_DBFS - sound.dBFS)
    return normalized.export(target_file, format="wav")


def analyze(file):
    """Computes EmotionProbabilities from the provided wave file"""
    global decibel
    (sample_rate, samples) = scipy.io.wavfile.read(file)
    buffer_length = len(samples)
    c_buffer = Vokaturi.SampleArrayC(buffer_length)
    if samples.ndim == 1:  # mono
        c_buffer[:] = samples[:] / 32768.0
    else:  # stereo
        c_buffer[:] = 0.5 * (samples[:, 0] + 0.0 + samples[:, 1]) / 32768.0

    voice = Vokaturi.Voice(sample_rate, buffer_length)
    voice.fill(buffer_length, c_buffer)
    quality = Vokaturi.Quality()
    ep = Vokaturi.EmotionProbabilities()
    voice.extract(quality, ep)
    a = ep if quality.valid and MAX_LOUDNESS + decibel > params.MIN_LOUDNESS else Vokaturi.EmotionProbabilities(0, 0, 0,
                                                                                                                0, 0)
    show(a)
    set_color(get_color(a))
    voice.destroy()


def progress(count, total, status=''):
    """Shows simple progress-bar style output"""
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))
    bar = '=' * filled_len + ' ' * (bar_len - filled_len)
    sys.stdout.write('[%s] %s %3d\r\n' % (bar, status, count))


def show(ep):
    """Shows simple progress-bar style output in terminal: provided EmotionProbabilities, loudness, and samplet-ime"""
    global decibel
    global sample_time
    progress(ep.neutrality * 100, 100, status='neutral')
    progress(ep.happiness * 100, 100, status='happiness')
    progress(ep.sadness * 100, 100, status='sadness')
    progress(ep.anger * 100, 100, status='anger')
    progress(ep.fear * 100, 100, status='fear')
    sys.stdout.write('\r\n')
    progress(min(100, 120 + decibel), 100, status='dBFS')
    progress(int(10 * sample_time), 100, status='SampleTime/10 secs')
    sys.stdout.flush()
    sys.stdout.write("\033[F")
    sys.stdout.write("\033[F")
    sys.stdout.write("\033[F")
    sys.stdout.write("\033[F")
    sys.stdout.write("\033[F")
    sys.stdout.write("\033[F")
    sys.stdout.write("\033[F")
    sys.stdout.write("\033[F")


def set_color(col):
    """Set the bulb to the provided color, or dim the current color if provided color is 0,0,0"""
    global prev_col
    global hue
    global dev
    if col[0] == 0 and col[1] == 0 and col[2] == 0:
        if prev_col[0] != 0 or prev_col[1] or prev_col[2] != 0:
            col[0] = int(prev_col[0] / 4)
            col[1] = int(prev_col[1] / 4)
            col[2] = int(prev_col[2] / 4)
    prev_col = col
    hue.set_color(col)
    set_neo(params.NEO_PIXELS, col)


def set_neo(k, col):
    """Set the neopixels 1..k to the provided color"""
    d = params.MAX_NEO_VALUE / 255
    for i in range(k):
        dev.set_pixel(i, int(d * col[0]), int(d * col[1]), int(d * col[2]))
    dev.show()


def set_neos(col0, col1, col2):
    """Set the neopixels to the provided colors"""
    dev.set_pixel(0, col0[0], col0[1], col0[2])
    dev.set_pixel(1, col1[0], col1[1], col1[2])
    dev.set_pixel(2, col2[0], col2[1], col2[2])
    dev.show()


def get_color(ep):
    """Returns a RGB color based on the provided EmotionProbabilities and params settings"""
    if params.DISCRETE:  # only show strongest emotion
        emo = 'neutrality'
        m = ep.neutrality
        if ep.happiness > m:
            emo = 'happiness'
            m = ep.happiness
        if ep.sadness > m:
            emo = 'sadness'
            m = ep.sadness
        if ep.anger > m:
            emo = 'anger'
            m = ep.anger
        if ep.fear > m:
            emo = 'fear'
            m = ep.fear
        col = copy.deepcopy(getattr(params, emo))
        if params.RELATIVE:
            m = math.sqrt(m)
            col[0] = int(m * col[0])
            col[1] = int(m * col[1])
            col[2] = int(m * col[2])
    else:
        print(params.DISCRETE, platform.processor())
        red = ep.neutrality * params.neutrality[0]
        red += ep.happiness * params.happiness[0]
        red += ep.sadness * params.sadness[0]
        red += ep.anger * params.anger[0]
        red += ep.fear * params.fear[0]

        green = ep.neutrality * params.neutrality[1]
        green += ep.happiness * params.happiness[1]
        green += ep.sadness * params.sadness[1]
        green += ep.anger * params.anger[1]
        green += ep.fear * params.fear[1]

        blue = ep.neutrality * params.neutrality[2]
        blue += ep.happiness * params.happiness[2]
        blue += ep.sadness * params.sadness[2]
        blue += ep.anger * params.anger[2]
        blue += ep.fear * params.fear[2]
        col = [int(red), int(green), int(blue)]
    return col


BUTTON = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON, GPIO.IN)
sample_time = params.RECORD_SECONDS
prev_color = [0, 0, 0]
decibel = 0.0
dev = apa102.APA102(num_led=3)
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

if __name__ == "__main__":
    global hue
    os.system('clear')
    set_neos([1, 0, 0], [0, 1, 0], [0, 0, 1])
    while True:
        counter = 1
        try:
            hue = MagicHue(params.MAC_ADDRESS, params.BULB_VERSION)
            if hue.check():
                break
            time.sleep(1)
        except Exception as e:
            col = [0, 0, 0]
            counter = (counter + 1) % 3  # 0,1,2
            col[counter] = 1
            set_neos(col, [0, 1, 0], [0, 0, 1])
            pass
    set_neos([0, 1, 0], [0, 1, 0], [0, 1, 0])
    try:
        while True:
            thread1 = RecordThread(1, "Recorder", 1)
            thread2 = AnalyzeThread(2, "Analyzer", 2)
            thread1.start()
            thread2.start()
            thread1.join()
            thread2.join()
            if os.path.exists(WAVE_FILENAME):
                os.rename(WAVE_FILENAME, WORK_FILENAME)
            if not GPIO.input(BUTTON):
                sample_time += 0.1
    except (RuntimeError, TypeError, NameError):
        stream.stop_stream()
        stream.close()
        p.terminate()
