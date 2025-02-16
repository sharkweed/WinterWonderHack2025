from time import sleep

import requests
import json
import argparse
import queue
import sys
import os
import sounddevice as sd
from gtts import gTTS
import time
import struct
import threading
from vosk import Model, KaldiRecognizer
import re
import asyncio
import queue
from pydub import AudioSegment
import numpy as np
from bleak import BleakClient, BleakScanner
import random
import emoji


url = "https://ollama.anolabz.com/api/generate"  # Include the full endpoint path

headers = {
    "Content-Type": "application/json"  # Fix the typo here
}

data_info = {
    "model": "ALIENTELLIGENCE/sarahv2",
    "prompt": "Pretend you are an AI girlfriend and be extry flirty from now on",
    "stream": False
}

SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "d86b8526-267d-413b-897e-84545131b842"

q = queue.Queue()
paused = False

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text

async def find_esp32():
    devices = await BleakScanner.discover()
    for d in devices:
        if d.name and "ESP32-S3" in d.name:
            return d.address
    return None

async def send_data(client, data):
    await client.write_gatt_char(CHARACTERISTIC_UUID, data.encode(), response=False)

def callback(indata, frames, time, status):
    global paused
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    if not paused:  # Ignore data if paused
        q.put(bytes(indata))

def pause_recording():
    global paused
    paused = True
    print("Recording paused.")

def resume_recording():
    global paused
    paused = False
    print("Recording resumed.")

def text_to_speech(message, file_index):
    """Convert text to speech and play it."""
    speech = gTTS(text=message, lang='en', slow=False)
    filename = f"audio_{file_index}.mp3"
    speech.save(filename)

    movement_thread = threading.Thread(target=mouth_movement, args=(filename,))
    movement_thread.start()
    # Play the audio while moving the mouth

    movement_thread.join()  # Wait for the movement to finish


def mouth_movement(audio_file, update_interval=0.45):
    audio = AudioSegment.from_file(audio_file)
    duration = audio.duration_seconds
    asyncio.run(move_servo(audio_file, duration))
    time.sleep(duration+4)
    resume_recording()

async def move_servo(filename, duration):
    try:
        data = ""
        address = await find_esp32()
        if not address:
            print("ESP32 not found")
            return

        os.startfile(filename)  # Plays the audio on Windows



        async with BleakClient(address) as client:
            data = f"{duration}\n"
            await send_data(client, data)

    except Exception as e:
        print(f"Error 2: {e}")

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    "-l", "--list-devices", action="store_true",
    help="show list of audio devices and exit")
args, remaining = parser.parse_known_args()
if args.list_devices:
    print(sd.query_devices())
    parser.exit(0)
parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    parents=[parser])
parser.add_argument(
    "-f", "--filename", type=str, metavar="FILENAME",
    help="audio file to store recording to")
parser.add_argument(
    "-d", "--device", type=int_or_str,
    help="input device (numeric ID or substring)")
parser.add_argument(
    "-r", "--samplerate", type=int, help="sampling rate")
parser.add_argument(
    "-m", "--model", type=str, help="language model; e.g. en-us, fr, nl; default is en-us")
args = parser.parse_args(remaining)


def remove_think_block(text):
    return re.sub(r'^.*?</think>\s*', '', text, flags=re.DOTALL)

def remove_emojis(text):
    return emoji.replace_emoji(text, replace='')  # Removes emojis

def main():
    try:
        if args.samplerate is None:
            device_info = sd.query_devices(args.device, "input")
            args.samplerate = int(device_info["default_samplerate"])

        model = Model(lang=args.model if args.model else "en-us")

        if args.filename:
            dump_fn = open(args.filename, "wb")
        else:
            dump_fn = None

        file_index = random.randint(0, 9999)  # Track audio file names
        with sd.RawInputStream(samplerate=args.samplerate, blocksize=8000, device=args.device,
                               dtype="int16", channels=1, callback=callback):
            print("#" * 80)
            print("Press Ctrl+C to stop the recording")
            print("#" * 80)

            response = requests.post(url, headers=headers, json=data_info)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx, 5xx)

            # Parse the response
            response_data = response.json()

            rec = KaldiRecognizer(model, args.samplerate)

            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = rec.Result()
                    print(result)
                    # Extract text from JSON response
                    text = json.loads(result).get("text", "").strip();

                    if text:

                        pause_recording()
                        #For all following prompt, role play as a flirty girl, and also keep the messages max 15 words:
                        message = text;
                        deepseek_info = {
                            "model": "ALIENTELLIGENCE/sarahv2",
                            "prompt": message,
                            "stream": False
                        }

                        try:
                            # Use the `json` parameter to automatically serialize `data` and set headers
                            response = requests.post(url, headers=headers, json=deepseek_info)
                            response.raise_for_status()  # Raise an exception for HTTP errors (4xx, 5xx)

                            # Parse the response
                            response_data = response.json()
                            actual_response = remove_emojis(remove_think_block(response_data.get("response")))
                            print(actual_response)

                            text_to_speech(actual_response, file_index)

                        except requests.exceptions.RequestException as e:
                            # Handle connection errors, timeouts, or HTTP errors
                            print(f"Error 1: {e}")
                        #text_to_speech(text, file_index)
                        file_index += 1  # Increment file index for next audio

                if dump_fn is not None:
                    dump_fn.write(data)

    except KeyboardInterrupt:
        print("\nDone")
        parser.exit(0)
    except Exception as e:
        parser.exit(type(e).__name__ + ": " + str(e))


if __name__ == "__main__":
    main()