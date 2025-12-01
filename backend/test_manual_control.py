import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_get_servo_positions():
    """Test the GET /get_servo_positions endpoint"""
    print("\n" + "="*60)
    print("TEST 1: Get Servo Positions")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/get_servo_positions")
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            data = response.json()
            assert "angles" in data, "Missing 'angles' in response"
            assert len(data["angles"]) == 6, f"Expected 6 angles, got {len(data['angles'])}"
            print("✅ TEST PASSED")
        else:
            print("❌ TEST FAILED: Non-200 status code")
            
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")

def test_manual_control_valid():
    """Test the POST /manual_control endpoint with valid angles"""
    print("\n" + "="*60)
    print("TEST 2: Manual Control - Valid Angles")
    print("="*60)
    
    payload = {
        "angles": [45, 60, 90, 120, 30, 0]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/manual_control", json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "success", "Status should be 'success'"
            assert data["angles"] == payload["angles"], "Angles should match"
            print("✅ TEST PASSED")
            print("\n👉 CHECK BACKEND TERMINAL for servo command output!")
        else:
            print("❌ TEST FAILED: Non-200 status code")
            
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")

def test_manual_control_invalid_count():
    """Test the POST /manual_control endpoint with wrong number of angles"""
    print("\n" + "="*60)
    print("TEST 3: Manual Control - Invalid Angle Count")
    print("="*60)
    
    payload = {
        "angles": [45, 60, 90]  # Only 3 angles instead of 6
    }
    
    try:
        response = requests.post(f"{BASE_URL}/manual_control", json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 400:
            print("✅ TEST PASSED: Correctly rejected invalid angle count")
        else:
            print("❌ TEST FAILED: Should return 400 for wrong angle count")
            
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")

def test_manual_control_out_of_range():
    """Test the POST /manual_control endpoint with out-of-range angles"""
    print("\n" + "="*60)
    print("TEST 4: Manual Control - Out of Range Angles")
    print("="*60)
    
    payload = {
        "angles": [45, 60, 90, 200, 30, 0]  # 200° is out of range
    }
    
    try:
        response = requests.post(f"{BASE_URL}/manual_control", json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 400:
            print("✅ TEST PASSED: Correctly rejected out-of-range angle")
        else:
            print("❌ TEST FAILED: Should return 400 for out-of-range angle")
            
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")

def test_manual_control_negative():
    """Test the POST /manual_control endpoint with negative angles"""
    print("\n" + "="*60)
    print("TEST 5: Manual Control - Negative Angles")
    print("="*60)
    
    payload = {
        "angles": [45, -30, 90, 120, 30, 0]  # -30° is invalid
    }
    
    try:
        response = requests.post(f"{BASE_URL}/manual_control", json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 400:
            print("✅ TEST PASSED: Correctly rejected negative angle")
        else:
            print("❌ TEST FAILED: Should return 400 for negative angle")
            
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")

def test_full_sequence():
    """Test a sequence of movements"""
    print("\n" + "="*60)
    print("TEST 6: Full Movement Sequence")
    print("="*60)
    
    positions = [
        [90, 90, 90, 90, 90, 0],    # Neutral
        [45, 45, 45, 45, 45, 90],   # All at 45°
        [135, 135, 135, 135, 135, 0],  # All at 135°
        [90, 90, 90, 90, 90, 0],    # Back to neutral
    ]
    
    try:
        for i, angles in enumerate(positions):
            print(f"\n  Step {i+1}: Moving to {angles}")
            response = requests.post(f"{BASE_URL}/manual_control", json={"angles": angles})
            
            if response.status_code == 200:
                print(f"  ✓ Success")
            else:
                print(f"  ✗ Failed: {response.json()}")
                return
            
            time.sleep(0.5)  # Small delay between movements
        
        print("\n✅ TEST PASSED: All movements executed")
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")

if __name__ == "__main__":
    print("\n🚀 Starting Manual Control API Tests")
    print("📍 Make sure the backend is running on http://localhost:5000\n")
    
    # Run all tests
    test_get_servo_positions()
    test_manual_control_valid()
    test_manual_control_invalid_count()
    test_manual_control_out_of_range()
    test_manual_control_negative()
    test_full_sequence()
    
    print("\n" + "="*60)
    print("🏁 All tests completed!")
    print("="*60)
