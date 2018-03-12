echo "Press Control C. Otherwise app will start in 5 seconds ..."
sleep 5 
amixer -c 1 set Capture 12DB
python3 ./emoLamp.py

