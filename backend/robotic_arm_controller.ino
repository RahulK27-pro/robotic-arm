#include <Servo.h>

/**
 * 6-DOF Robotic Arm Controller
 * Receives angle commands from Python backend via Serial
 * Format: <angle1,angle2,angle3,angle4,angle5,angle6>
 * Sends acknowledgment: K
 */

// Create servo objects
Servo servo1; // Base Rotation
Servo servo2; // Shoulder
Servo servo3; // Elbow
Servo servo4; // Wrist Pitch
Servo servo5; // Wrist Roll
Servo servo6; // Gripper

// Servo pins (PWM-capable pins on Arduino Uno)
const int SERVO_PINS[6] = {3, 5, 6, 9, 10, 11};

void setup() {
  // Initialize serial communication at 115200 baud
  Serial.begin(115200);
  
  // Attach servos to their respective pins
  servo1.attach(SERVO_PINS[0]); // Pin 3  - Base
  servo2.attach(SERVO_PINS[1]); // Pin 5  - Shoulder
  servo3.attach(SERVO_PINS[2]); // Pin 6  - Elbow
  servo4.attach(SERVO_PINS[3]); // Pin 9  - Wrist Pitch
  servo5.attach(SERVO_PINS[4]); // Pin 10 - Wrist Roll
  servo6.attach(SERVO_PINS[5]); // Pin 11 - Gripper
  
  // Initialize all servos to neutral position
  servo1.write(90);
  servo2.write(90);
  servo3.write(90);
  servo4.write(90);
  servo5.write(90);
  servo6.write(0); // Gripper starts closed
  
  // Send ready message
  Serial.println("6-DOF Robotic Arm Ready");
  Serial.println("Waiting for commands...");
}

void loop() {
  // Check if data is available on serial port
  if (Serial.available() > 0) {
    // Read incoming packet until newline
    String packet = Serial.readStringUntil('\n');
    packet.trim(); // Remove any whitespace
    
    // Validate packet format: <angle1,angle2,angle3,angle4,angle5,angle6>
    if (packet.startsWith("<") && packet.endsWith(">")) {
      // Remove < and > brackets
      packet = packet.substring(1, packet.length() - 1);
      
      // Parse 6 comma-separated angles
      int angles[6];
      int angleCount = parseAngles(packet, angles);
      
      // Verify we got exactly 6 angles
      if (angleCount == 6) {
        // Move all servos to new positions
        servo1.write(angles[0]);
        servo2.write(angles[1]);
        servo3.write(angles[2]);
        servo4.write(angles[3]);
        servo5.write(angles[4]);
        servo6.write(angles[5]);
        
        // Send acknowledgment to Python
        Serial.println("K");
        
        // Optional: Print debug info (comment out for production)
        // Serial.print("Moved to: ");
        // for (int i = 0; i < 6; i++) {
        //   Serial.print(angles[i]);
        //   if (i < 5) Serial.print(",");
        // }
        // Serial.println();
      } else {
        Serial.println("ERROR: Expected 6 angles");
      }
    } else {
      Serial.println("ERROR: Invalid packet format");
    }
  }
}

/**
 * Parse comma-separated angles from string
 * Returns: number of angles parsed
 */
int parseAngles(String data, int angles[]) {
  int index = 0;
  int lastIndex = 0;
  int angleCount = 0;
  
  // Parse each angle separated by comma
  for (int i = 0; i < 6; i++) {
    int commaIndex = data.indexOf(',', lastIndex);
    
    String angleStr;
    if (commaIndex == -1) {
      // Last angle (no comma after it)
      angleStr = data.substring(lastIndex);
      if (angleStr.length() == 0) break;
      angles[i] = parseAndClamp(angleStr);
      angleCount++;
      break;
    } else {
      // Extract angle between commas
      angleStr = data.substring(lastIndex, commaIndex);
      if (angleStr.length() == 0) break;
      angles[i] = parseAndClamp(angleStr);
      angleCount++;
      lastIndex = commaIndex + 1;
    }
  }
  
  return angleCount;
}

/**
 * Convert string to integer and clamp to 0-180 range
 */
int parseAndClamp(String angleStr) {
  int angle = angleStr.toInt();
  // Constrain to valid servo range
  return constrain(angle, 0, 180);
}
