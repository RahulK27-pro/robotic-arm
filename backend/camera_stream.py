import cv2
import threading
import time

class ThreadedCamera:
    """
    Threaded Camera Capture for Robust Low-Latency Video.
    
    Features:
    - Runs capture in a separate daemon thread to prevent UI blocking.
    - Auto-reconnects if the camera signal is lost.
    - Uses a lock to ensure thread-safe frame access.
    - Keeps buffer size low to minimize latency.
    """
    def __init__(self, src=0):
        self.src = src
        self.cap = cv2.VideoCapture(self.src)
        
        # Optimize for low latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Threading primitives
        self.lock = threading.Lock()
        self.running = True
        
        # Initial frame reading
        self.grabbed, self.frame = self.cap.read()
        if not self.grabbed:
            print(f"[ThreadedCamera] Warning: Could not read from source {self.src} at startup.")
        
        # Start the capture thread
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()
        print(f"[ThreadedCamera] Camera started on source {self.src}")

    def update(self):
        """
        Main thread loop: Reads frames continuously.
        Handles auto-reconnection on failure.
        """
        while self.running:
            try:
                grabbed, frame = self.cap.read()
                
                if grabbed:
                    # Thread-safe write
                    with self.lock:
                        self.grabbed = grabbed
                        self.frame = frame
                else:
                    # Signal lost logic
                    print("[ThreadedCamera] Msg: Signal lost (read returned False). Reconnecting...")
                    self.reconnect()
                    
            except Exception as e:
                print(f"[ThreadedCamera] Error in capture loop: {e}")
                self.reconnect()

    def read(self):
        """
        Returns the latest available frame.
        Use this in your main loop.
        """
        with self.lock:
            if self.grabbed and self.frame is not None:
                return self.frame.copy()
            else:
                return None

    def reconnect(self):
        """
        Attempts to release and restart the camera connection.
        """
        # Release existing
        if self.cap:
            self.cap.release()
            
        time.sleep(1.0) # Wait before retry
        
        print("[ThreadedCamera] Attempting to reconnect...")
        self.cap = cv2.VideoCapture(self.src)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Quick check
        if self.cap.isOpened():
             print("[ThreadedCamera] Reconnected successfully.")
        else:
             print("[ThreadedCamera] Reconnection failed.")

    def stop(self):
        """
        Stops the thread and releases resources.
        """
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.cap.release()
        print("[ThreadedCamera] Camera stopped.")
