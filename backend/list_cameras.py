import cv2

def list_ports():
    is_working = True
    dev_port = 0
    working_ports = []
    available_ports = []
    while dev_port < 10:
        camera = cv2.VideoCapture(dev_port)
        if not camera.isOpened():
            is_working = False
            print(f"Port {dev_port} is not working.")
        else:
            is_reading, img = camera.read()
            w = camera.get(3)
            h = camera.get(4)
            if is_reading:
                print(f"Port {dev_port} is working and reads images ({w}x{h})")
                working_ports.append(dev_port)
            else:
                print(f"Port {dev_port} is present but not reading.")
                available_ports.append(dev_port)
        dev_port += 1
    return working_ports, available_ports

if __name__ == "__main__":
    print("Scanning for camera ports...")
    list_ports()
