# EmoLamp
The idea behind the Vocal-Emotion Lamp is rather simple: to use a small affordable computer that can continually recognize emotion from the human voice and then visualize the result of the analysis, effortlessly and enjoyably.

The implementation of this idea uses the small and inexpensive Raspberry Pi computer, extended with a far-field microphone expansion board. The software that performs the emotion recognition directly from the microphone input, is based on the open-source version of  the Vokaturi emotion recognition library. Vokaturi uses algorithms that have been designed by Paul Boersma, author of the world’s leading speech analysis software Praat.

Once an emotion has been recognized, the Raspberry Pi communicates over a Bluetooth connection with a smart light bulb, changing its color and intensity, bases on the recognized emotion(s). The overall hardware cost should be below one hundred dollars. Remarkably, when compared to many other voice enabled devices, the Emotion Lamp does not require an internet-connection to work. I.e., voice recordings will never leave the device, won't even be stored on devices, only buffered for a few seconds, during processing.

More detail:
https://trailblazer.intuitlabs.com/blog/emotion-lamp/