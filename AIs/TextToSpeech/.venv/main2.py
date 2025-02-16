from time import sleep

from bleak import BleakClient, BleakScanner
import asyncio
import struct

# Use the same UUIDs as defined in the ESP32 code
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "d86b8526-267d-413b-897e-84545131b842"


async def find_esp32():
    devices = await BleakScanner.discover()
    for d in devices:
        if d.name and "ESP32-S3" in d.name:
            return d.address
    return None


async def send_data(client, data):
    await client.write_gatt_char(CHARACTERISTIC_UUID, data.encode(), response=False)


# Example usage
async def main():
    address = await find_esp32()
    if not address:
        print("ESP32 not found")
        return
    # Send a test message
    async with BleakClient(address) as client:
        print(f"Connected to {address}")

        while True:
            await send_data(client, "0")
            await asyncio.sleep(0.5)  # Reduce delay
            await send_data(client, "90")
            await asyncio.sleep(0.5)  # Reduce delay


if __name__ == "__main__":
    asyncio.run(main())