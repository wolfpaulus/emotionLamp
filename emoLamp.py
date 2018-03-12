# emoLamp.py
# Author Wolf Paulus, Intuit IAT
# Version 2018-03-10

import os
import sys
import platform
import math
import copy
import time
import threading
import pyaudio
import wave
import scipy.io.wavfile
from pydub import AudioSegment
from magicblue import MagicBlue, Effect
import apa102
import params
import RPi.GPIO as GPIO

sys.path.append('./OpenVokaturi-3-0/api')
import Vokaturi

# Hardware 'pi3b.so' or 'piZero.so'
print(platform.machine())
if platform.machine() == 'armv7l':
    Vokaturi.load('./OpenVokaturi-3-0/lib/open/linux/pi3b.so')
    print('pi3b.so loaded')
else:
    Vokaturi.load('./OpenVokaturi-3-0/lib/open/linux/piZero.so')
    print('piZero.so loaded')

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
        self.check()
        self.bulb.set_color(rgb)

    def check(self):
        if not self.bulb.test_connection:
            return self.bulb.connect()
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
    """Shows simple progress-bar style output in the terminal the provided EmotionProbabilities, loudness, and sampletime"""
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
    if 0 < params.NEO_PIXELS:
        d = params.MAX_NEO_VALUE / 255
        for i in range(params.NEO_PIXELS):
            dev.set_pixel(i, int(d * col[0]), int(d * col[1]), int(d * col[2]))
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
dev.set_pixel(0, 1, 0, 0)
dev.set_pixel(1, 0, 1, 0)
dev.set_pixel(2, 0, 0, 1)
dev.show()
hue = MagicHue(params.MAC_ADDRESS, params.BULB_VERSION)
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

if __name__ == "__main__":
    os.system('clear')
    while True:
        try:
            if hue.check():
                break
            time.sleep(1)
        except Exception as e:
            pass
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
            state = GPIO.input(BUTTON)
            if not GPIO.input(BUTTON):
                sample_time += 0.1
    except (RuntimeError, TypeError, NameError):
        stream.stop_stream()
        stream.close()
        p.terminate()
