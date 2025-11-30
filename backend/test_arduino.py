import serial
import time
import sys

def test_connection():
    port = 'COM4'
    baud = 115200
    
    print(f"🔌 Attempting to connect to {port} at {baud} baud...")
    print("⚠️  IMPORTANT: Please ensure the Arduino Serial Monitor is CLOSED.")
    
    try:
        ser = serial.Serial(port, baud, timeout=2)
        time.sleep(2) # Wait for reset
        print("✅ Connection Successful!")
        
        # Clear buffer
        if ser.in_waiting:
            print(f"   Startup msg: {ser.read_all().decode('utf-8', errors='ignore').strip()}")
            
        # Send test packet
        packet = "<90,90,90,90,90,10>"
        print(f"📤 Sending test packet: {packet}")
        ser.write(packet.encode('utf-8'))
        
        # Wait for reply
        start = time.time()
        while time.time() - start < 3:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                print(f"📥 Received: {line}")
                if "ARDUINO" in line:
                    print("🎉 SUCCESS! Communication verified.")
                    ser.close()
                    return
        
        print("❌ No reply received within 3 seconds.")
        ser.close()
        
    except serial.SerialException as e:
        print(f"\n❌ CONNECTION FAILED: {e}")
        if "Access is denied" in str(e):
            print("👉 CAUSE: The port is likely open in another app (like Arduino Serial Monitor).")
            print("👉 FIX: Close the Serial Monitor and try again.")

if __name__ == "__main__":
    test_connection()
