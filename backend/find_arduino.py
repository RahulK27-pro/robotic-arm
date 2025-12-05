"""
Arduino Port Finder
Scans all COM ports to find Arduino and test communication
"""

import serial
import serial.tools.list_ports
import time

def find_arduino():
    print("=" * 60)
    print("Arduino Port Finder")
    print("=" * 60)
    
    # List all available ports
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("\n❌ No COM ports detected!")
        print("   - Check if Arduino is connected via USB")
        print("   - Try a different USB cable")
        return
    
    print(f"\n📍 Found {len(ports)} COM port(s):\n")
    for port in ports:
        print(f"   {port.device}: {port.description}")
    
    print("\n🔍 Testing each port for Arduino response...\n")
    
    # Test each port
    arduino_found = False
    for port in ports:
        port_name = port.device
        print(f"Testing {port_name}... ", end="", flush=True)
        
        try:
            # Try to open the port
            ser = serial.Serial(port_name, 115200, timeout=2)
            time.sleep(2)  # Wait for Arduino reset
            
            # Flush any startup messages
            if ser.in_waiting:
                startup = ser.read_all().decode('utf-8', errors='ignore')
                if "Robotic Arm" in startup or "Ready" in startup:
                    print(f"✅ ARDUINO FOUND!")
                    print(f"   Startup message: {startup.strip()}")
                    arduino_found = True
                    
                    # Test command
                    print(f"   Sending test command...", end="", flush=True)
                    ser.write(b"<90,90,90,90,90,45>")
                    time.sleep(0.1)
                    
                    if ser.in_waiting:
                        response = ser.readline().decode('utf-8', errors='ignore').strip()
                        if response == 'K':
                            print(f" ✅ Got 'K' acknowledgment")
                            print(f"\n🎉 SUCCESS! Use this port in app.py: port='{port_name}'")
                        else:
                            print(f" ⚠️  Got: '{response}'")
                    else:
                        print(f" ❌ No response")
                    
                    ser.close()
                    print()
                    continue
            
            # Try sending test command anyway
            ser.write(b"<90,90,90,90,90,45>")
            time.sleep(0.1)
            
            if ser.in_waiting:
                response = ser.readline().decode('utf-8', errors='ignore').strip()
                if response == 'K':
                    print(f"✅ ARDUINO FOUND (responds with 'K')")
                    print(f"\n🎉 SUCCESS! Use this port in app.py: port='{port_name}'")
                    arduino_found = True
                else:
                    print(f"⚠️  Device responds but not Arduino (got: '{response}')")
            else:
                print("❌ No response")
            
            ser.close()
            
        except serial.SerialException as e:
            print(f"❌ Can't access ({str(e)[:30]}...)")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    
    if not arduino_found:
        print("\n⚠️  Arduino not detected on any port")
        print("\nTroubleshooting:")
        print("  1. Upload robotic_arm_controller.ino to Arduino first")
        print("  2. Close Arduino Serial Monitor")
        print("  3. Try unplugging and replugging USB cable")
        print("  4. Check Device Manager for Arduino COM port")
    else:
        print("\n✅ Arduino is ready for manual control!")
    
    print("=" * 60)

if __name__ == "__main__":
    find_arduino()
    input("\nPress Enter to exit...")
