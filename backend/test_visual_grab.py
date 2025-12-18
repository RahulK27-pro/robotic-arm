"""
Visual Grab System - Integration Test

Tests the complete visual grab workflow:
1. Distance estimation
2. Inverse kinematics
3. Grab controller state machine
4. API endpoints
"""

import sys
import time
import requests

# Test Configuration
API_BASE = "http://localhost:5000"
TEST_OBJECT = "cube"  # 3cm test cube


def test_distance_estimation():
    """Test distance estimation module"""
    print("\n" + "=" * 60)
    print("TEST 1: Distance Estimation Module")
    print("=" * 60)
    
    from brain.distance_estimator import calculate_distance, FOCAL_LENGTH_DEFAULT
    
    # Test with 3cm cube at various pixel widths
    test_cases = [
        (165, 20.2),   # 165px → ~20cm
        (110, 30.3),   # 110px → ~30cm
        (83, 40.1),    # 83px → ~40cm
    ]
    
    print(f"\nUsing focal length: {FOCAL_LENGTH_DEFAULT}px")
    print(f"Object width: 3.0cm (test cube)\n")
    
    all_passed = True
    for pixel_width, expected_dist in test_cases:
        distance = calculate_distance(FOCAL_LENGTH_DEFAULT, 3.0, pixel_width)
        error = abs(distance - expected_dist)
        status = "✅" if error < 1.0 else "❌"
        
        print(f"{status} {pixel_width}px → {distance:.1f}cm (expected {expected_dist:.1f}cm, error: {error:.1f}cm)")
        
        if error >= 1.0:
            all_passed = False
    
    return all_passed


def test_inverse_kinematics():
    """Test visual IK solver"""
    print("\n" + "=" * 60)
    print("TEST 2: Visual IK Solver")
    print("=" * 60)
    
    from brain.visual_ik_solver import get_wrist_angles, check_reachability
    
    # Test reachability and angle calculation
    test_distances = [
        (20.0, True),   # Should be reachable
        (25.0, True),   # Should be reachable
        (30.0, True),   # Should be reachable
        (35.0, True),   # Should be reachable
        (40.0, False),  # Should be out of reach
    ]
    
    print("\nReachability and IK Tests:\n")
    
    all_passed = True
    for distance, should_reach in test_distances:
        reachable, reason, wrist_dist = check_reachability(distance, 5.0)
        
        if reachable != should_reach:
            print(f"❌ {distance}cm: Expected {'reachable' if should_reach else 'unreachable'}, got {reason}")
            all_passed = False
            continue
        
        if reachable:
            angles = get_wrist_angles(distance, 5.0)
            if angles:
                shoulder, elbow = angles
                # Check angles are within servo limits
                if 0 <= shoulder <= 180 and 0 <= elbow <= 180:
                    print(f"✅ {distance}cm: Reachable (Sh: {shoulder:.1f}°, El: {elbow:.1f}°)")
                else:
                    print(f"❌ {distance}cm: Angles out of range (Sh: {shoulder:.1f}°, El: {elbow:.1f}°)")
                    all_passed = False
            else:
                print(f"❌ {distance}cm: IK calculation failed")
                all_passed = False
        else:
            print(f"✅ {distance}cm: Correctly identified as unreachable")
    
    return all_passed


def test_api_endpoints():
    """Test API endpoints"""
    print("\n" + "=" * 60)
    print("TEST 3: API Endpoints")
    print("=" * 60)
    
    print("\nChecking backend status...")
    
    try:
        # Test 1: Backend status
        response = requests.get(f"{API_BASE}/status", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Backend connected: {data.get('backend')}")
            print(f"   Vision: {data.get('vision')}")
            print(f"   Robot mode: {data.get('robot_mode')}")
        else:
            print(f"❌ Backend status check failed: {response.status_code}")
            return False
        
        # Test 2: Visual grab status endpoint
        print("\nTesting visual grab status endpoint...")
        response = requests.get(f"{API_BASE}/visual_grab_status", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Visual grab status: {data.get('state')}")
            print(f"   Active: {data.get('active')}")
        else:
            print(f"❌ Visual grab status check failed: {response.status_code}")
            return False
        
        # Test 3: Detection endpoint
        print("\nTesting detection endpoint...")
        response = requests.get(f"{API_BASE}/get_detection_result", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Detection endpoint working")
            if data.get('status') == 'found':
                print(f"   Found {data.get('count')} object(s)")
                for det in data.get('data', []):
                    obj_name = det.get('object_name')
                    distance = det.get('distance_cm', -1)
                    if distance > 0:
                        print(f"   - {obj_name}: {distance:.1f}cm")
                    else:
                        print(f"   - {obj_name}: distance unknown")
            else:
                print(f"   Status: {data.get('status')}")
        else:
            print(f"❌ Detection check failed: {response.status_code}")
            return False
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Is it running on port 5000?")
        return False
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False


def test_grab_workflow_simulation():
    """Simulate grab workflow (without actual robot movement)"""
    print("\n" + "=" * 60)
    print("TEST 4: Grab Workflow Simulation")
    print("=" * 60)
    
    from brain.grab_controller import GrabState
    
    print("\nSimulating state transitions:")
    states = [
        GrabState.IDLE,
        GrabState.ALIGNING,
        GrabState.APPROACHING,
        GrabState.GRAB_READY,
        GrabState.GRABBING,
        GrabState.COMPLETE
    ]
    
    for state in states:
        print(f"   {state.value}")
    
    print("\n✅ State machine structure verified")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("VISUAL GRAB SYSTEM - INTEGRATION TEST")
    print("=" * 60)
    
    results = {}
    
    # Run tests
    results['distance_estimation'] = test_distance_estimation()
    results['inverse_kinematics'] = test_inverse_kinematics()
    results['api_endpoints'] = test_api_endpoints()
    results['grab_workflow'] = test_grab_workflow_simulation()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name.replace('_', ' ').title()}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nNext steps:")
        print("1. Place a 3cm cube in front of the camera")
        print("2. Use the frontend or API to trigger: POST /start_visual_grab {'target_object': 'cube'}")
        print("3. Monitor progress: GET /visual_grab_status")
    else:
        print("\n⚠️ SOME TESTS FAILED")
        print("Please review the errors above.")
    
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
