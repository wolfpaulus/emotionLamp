#Mac address of the Lightbulb
MAC_ADDRESS = 'f8:1d:78:63:45:9d'

# Firmware Version in Lightbulb
BULB_VERSION = 10

# Sample time (i.e. length of the record that will be analyzed)
RECORD_SECONDS = 1.0

# Minimal loudness in sound input required for analysis. [0..100]
MIN_LOUDNESS = 63

# Show color of strongest emotion vs. mixing color by emotion strength
DISCRETE = True

# Show light intensity proportional to emotion strength (always true in none discrete mode)
RELATIVE = True

# Color RGB for emotions [int(red),int(red),int(green),int(blue)] all values [0..255]
neutrality = [0,255,0] # green
happiness = [255,90,0] # orange
sadness = [0,0,255] # blue
anger = [255,0,0] # red
fear = [255,0,255] # pink

# Use on device NEO-Pixels [0..3] where 0 means to not used them and 3 means use all off them
NEO_PIXELS = 3

# Maximal brightness for NEO-Pixels [0..255]
MAX_NEO_VALUE = 16
