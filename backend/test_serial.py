"""
Quick Serial Test Script
Tests if Arduino is responding on the specified COM port
"""

import serial
import time

PORT = 'COM4'  # Change if your Arduino is on a different port
BAUDRATE = 115200

def test_serial_connection():
    print("=" * 50)
    print("Arduino Serial Connection Test")
    print("=" * 50)
    
    try:
        # Open serial connection
        print(f"\n1. Opening serial port {PORT}...")
        ser = serial.Serial(PORT, BAUDRATE, timeout=2)
        time.sleep(2)  # Wait for Arduino to reset
        
        # Read startup message
        if ser.in_waiting:
            startup = ser.read_all().decode('utf-8', errors='ignore')
            print(f"   ✅ Arduino says: {startup.strip()}")
        
        # Send test command
        print("\n2. Sending test command: <90,90,90,90,90,45>")
        test_cmd = "<90,90,90,90,90,45>"
        ser.write(test_cmd.encode('utf-8'))
        
        # Wait for response
        time.sleep(0.1)
        if ser.in_waiting:
            response = ser.readline().decode('utf-8', errors='ignore').strip()
            if response == 'K':
                print(f"   ✅ Received acknowledgment: '{response}'")
                print("\n✅ SUCCESS! Arduino is responding correctly.")
            else:
                print(f"   ⚠️  Unexpected response: '{response}'")
        else:
            print("   ❌ No response from Arduino")
        
        # Close connection
        ser.close()
        print("\n3. Serial port closed.")
        
    except serial.SerialException as e:
        print(f"\n❌ ERROR: Could not open {PORT}")
        print(f"   Details: {e}")
        print("\nTroubleshooting:")
        print("  - Check if Arduino is connected")
        print("  - Verify correct COM port in Device Manager")
        print("  - Close Arduino Serial Monitor if open")
        print("  - Try a different USB cable")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_serial_connection()
    input("\nPress Enter to exit...")
