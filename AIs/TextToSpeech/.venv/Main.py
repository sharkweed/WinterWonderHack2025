#!/usr/bin/env python3

import argparse
import queue
import sys
import os
import sounddevice as sd
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import numpy as np
import time
from bleak import BleakClient, BleakScanner
import asyncio
import struct
import threading
import json
from vosk import Model, KaldiRecognizer


SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "d86b8526-267d-413b-897e-84545131b842"

q = queue.Queue()

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

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

async def find_esp32():
    devices = await BleakScanner.discover()
    for d in devices:
        if d.name and "ESP32-S3" in d.name:
            return d.address
    return None

async def send_data(data):
    address = await find_esp32()
    if not address:
        print("ESP32 not found")
        return
    async with BleakClient(address) as client:
        # Check if the device is connected
        if client.is_connected:
            print(f"Connected to {address}")
            await client.write_gatt_char(CHARACTERISTIC_UUID, data.encode())
            print(f"Sent: {data}")
        else:
            print(f"Failed to connect to {address}")


def mouth_movement(audio_file, update_interval=0.5):
    try:
        time.sleep(2)  # Give connection time to establish
        audio = AudioSegment.from_file(audio_file)
        samples = np.array(audio.get_array_of_samples())
        sample_rate = audio.frame_rate
        chunk_size = int(sample_rate * update_interval)

        num_chunks = len(samples) // chunk_size
        print(f"Processing {num_chunks} audio chunks...")
        data = ""

        for i in range(num_chunks):
            chunk = samples[i * chunk_size:(i + 1) * chunk_size]
            norm_volume = np.linalg.norm(chunk) / len(chunk)
            servo_position = int(np.clip(norm_volume * 0.3, 0, 90))

            # Send the servo position as a string followed by newline
            data = f"{servo_position}\n"
            print(f"Sent: {servo_position}")
            data += str(servo_position) + " "
            print(f"hmmmm {data}")
            time.sleep(update_interval)


        # loop = asyncio.get_event_loop()
        # loop.run_until_complete(send_data(data))
        asyncio.run(send_data(data))
    except Exception as e:
        print(f"Error: {e}")



def text_to_speech(message, file_index):
    """Convert text to speech and play it."""
    speech = gTTS(text=message, lang='en', slow=False)
    filename = f"audio_{file_index}.mp3"
    speech.save(filename)

    #asyncio.run(mouth_movement(filename))

    # Start mouth movement in a separate thread (to sync with playback)
    movement_thread = threading.Thread(target=mouth_movement, args=(filename,))
    movement_thread.start()

    # Play the audio while moving the mouth
    os.startfile(filename)  # Plays the audio on Windows

    movement_thread.join()  # Wait for the movement to finish


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

        file_index = 0  # Track audio file names
        with sd.RawInputStream(samplerate=args.samplerate, blocksize=8000, device=args.device,
                               dtype="int16", channels=1, callback=callback):
            print("#" * 80)
            print("Press Ctrl+C to stop the recording")
            print("#" * 80)

            rec = KaldiRecognizer(model, args.samplerate)
            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = rec.Result()
                    print(result)

                    # Extract text from JSON response
                    text = json.loads(result).get("text", "").strip()
                    if text:
                        text_to_speech(text, file_index)
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
