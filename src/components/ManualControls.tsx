import { useState, useEffect, useCallback, useRef } from "react";
import { useLogs } from "@/context/LogContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, Settings, Save, Play, StopCircle } from "lucide-react";
import { toast } from "sonner";

interface Position {
  base: number;
  shoulder: number;
  elbow: number;
  wristPitch: number;
  wristRoll: number;
  gripper: number;
  speed: number;
}

const API_BASE = "http://localhost:5000";

// Throttle hook - limits function calls to once per delay period
const useThrottle = (callback: (...args: any[]) => void, delay: number) => {
  const lastCall = useRef(0);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  return useCallback(
    (...args: any[]) => {
      const now = Date.now();
      const timeSinceLastCall = now - lastCall.current;

      if (timeSinceLastCall >= delay) {
        // Execute immediately if enough time has passed
        lastCall.current = now;
        callback(...args);
      } else {
        // Schedule for later if called too soon
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => {
          lastCall.current = Date.now();
          callback(...args);
        }, delay - timeSinceLastCall);
      }
    },
    [callback, delay]
  );
};

const ManualControls = () => {
  const { addLog } = useLogs();
  const [isOpen, setIsOpen] = useState(true);
  const [base, setBase] = useState([90]);
  const [shoulder, setShoulder] = useState([90]);
  const [elbow, setElbow] = useState([90]);
  const [wristPitch, setWristPitch] = useState([90]);
  const [wristRoll, setWristRoll] = useState([90]);
  const [gripper, setGripper] = useState([90]);
  const [speed, setSpeed] = useState([1000]);
  const [savedPositions, setSavedPositions] = useState<Position[]>([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"connected" | "disconnected">("disconnected");

  // Send angles to backend
  const sendAnglesToBackend = async (angles: number[]) => {
    try {
      const response = await fetch(`${API_BASE}/manual_control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ angles }),
      });

      if (!response.ok) {
        const data = await response.json();
        console.error("Command failed:", data.error);
      }
    } catch (error) {
      console.error("Connection error:", error);
    }
  };

  // Throttled version - sends at most once every 100ms (10 updates/sec)
  const throttledSend = useThrottle(sendAnglesToBackend, 100);

  // SSE Connection for real-time updates
  useEffect(() => {
    // Skip if user is dragging to avoid jitter
    if (isDragging || isSending) return;

    const eventSource = new EventSource(`${API_BASE}/servo_stream`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setConnectionStatus("connected");

        // Update sliders with actual servo positions
        // Only update if not dragging to prevent fighting the user
        if (!isDragging && !isSending) {
          const angles = data.angles;
          setBase([angles[0]]);
          setShoulder([angles[1]]);
          setElbow([angles[2]]);
          setWristPitch([angles[3]]);
          setWristRoll([angles[4]]);
          setGripper([angles[5]]);
        }
      } catch (error) {
        console.error("Error parsing SSE data:", error);
      }
    };

    eventSource.onerror = (error) => {
      console.error("SSE Error:", error);
      setConnectionStatus("disconnected");
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [isDragging, isSending]);

  // Handler for continuous slider  movement (while dragging)
  const handleSliderChange = (setter: (val: number[]) => void) => (value: number[]) => {
    setIsDragging(true);
    setter(value);

    // Send current angles (throttled to 50ms)
    const currentAngles = [
      value === base ? value[0] : base[0],
      value === shoulder ? value[0] : shoulder[0],
      value === elbow ? value[0] : elbow[0],
      value === wristPitch ? value[0] : wristPitch[0],
      value === wristRoll ? value[0] : wristRoll[0],
      value === gripper ? value[0] : gripper[0],
    ];

    // Get the correct current angle for the slider being moved
    if (setter === setBase) currentAngles[0] = value[0];
    else if (setter === setShoulder) currentAngles[1] = value[0];
    else if (setter === setElbow) currentAngles[2] = value[0];
    else if (setter === setWristPitch) currentAngles[3] = value[0];
    else if (setter === setWristRoll) currentAngles[4] = value[0];
    else if (setter === setGripper) currentAngles[5] = value[0];

    throttledSend(currentAngles);
  };

  // Handler for when slider is released
  const handleSliderCommit = () => {
    setIsDragging(false);

    // Send final angles one more time (unthrottled)
    const finalAngles = [
      base[0],
      shoulder[0],
      elbow[0],
      wristPitch[0],
      wristRoll[0],
      gripper[0],
    ];
    sendAnglesToBackend(finalAngles);
    addLog("SERVO", `Manual Move: ${finalAngles.map(a => a.toFixed(1)).join(", ")}`);
  };

  const handleSavePosition = () => {
    const newPosition: Position = {
      base: base[0],
      shoulder: shoulder[0],
      elbow: elbow[0],
      wristPitch: wristPitch[0],
      wristRoll: wristRoll[0],
      gripper: gripper[0],
      speed: speed[0],
    };
    setSavedPositions([...savedPositions, newPosition]);
    toast.success(`Position ${savedPositions.length + 1} saved`, {
      description: `Speed: ${speed[0]}ms`,
    });
  };

  const handlePlayMovements = async () => {
    if (savedPositions.length === 0) {
      toast.error("No saved positions", {
        description: "Save at least one position first",
      });
      return;
    }

    setIsPlaying(true);
    setIsSending(true);
    toast.info("Playing movements", {
      description: `${savedPositions.length} positions queued`,
    });

    // Execute each saved position sequentially
    for (let i = 0; i < savedPositions.length; i++) {
      if (!isPlaying && i > 0) break;

      const pos = savedPositions[i];
      const angles = [
        pos.base,
        pos.shoulder,
        pos.elbow,
        pos.wristPitch,
        pos.wristRoll,
        pos.gripper,
      ];

      await sendAnglesToBackend(angles);

      // Wait based on saved speed
      if (i < savedPositions.length - 1) {
        await new Promise((resolve) => setTimeout(resolve, pos.speed));
      }
    }

    setIsPlaying(false);
    setIsSending(false);
    toast.success("Playback complete");
  };

  const handleStopMovement = () => {
    setIsPlaying(false);
    setIsSending(false);
    toast.warning("Movement stopped", {
      description: "Servo motion halted",
    });
  };

  return (
    <Card className="bg-card border-border">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CardHeader className="pb-3">
          <CollapsibleTrigger className="flex items-center justify-between w-full hover:opacity-80 transition-opacity">
            <CardTitle className="text-sm data-label flex items-center gap-2">
              <Settings className="h-4 w-4 text-warning" />
              ENGINEER MODE - MANUAL OVERRIDE
              <span
                className={`ml-2 text-xs ${connectionStatus === "connected"
                  ? "text-status-active"
                  : "text-critical"
                  }`}
              >
                {connectionStatus === "connected" ? "🟢 CONNECTED" : "🔴 DISCONNECTED"}
              </span>
            </CardTitle>
            <ChevronDown
              className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""
                }`}
            />
          </CollapsibleTrigger>
        </CardHeader>

        <CollapsibleContent>
          <CardContent className="space-y-6">
            {/* Servo Controls */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">SERVO 1 - BASE ROTATION</span>
                <span className="data-value text-lg">{base[0].toFixed(2)}°</span>
              </div>
              <Slider
                value={base}
                onValueChange={handleSliderChange(setBase)}
                onValueCommit={handleSliderCommit}
                max={180}
                step={0.01}
                className="w-full"
                disabled={isSending}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0°</span>
                <span>180°</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">SERVO 2 - SHOULDER</span>
                <span className="data-value text-lg">{shoulder[0].toFixed(2)}°</span>
              </div>
              <Slider
                value={shoulder}
                onValueChange={handleSliderChange(setShoulder)}
                onValueCommit={handleSliderCommit}
                max={180}
                step={0.01}
                className="w-full"
                disabled={isSending}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0°</span>
                <span>180°</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">SERVO 3 - ELBOW</span>
                <span className="data-value text-lg">{elbow[0].toFixed(2)}°</span>
              </div>
              <Slider
                value={elbow}
                onValueChange={handleSliderChange(setElbow)}
                onValueCommit={handleSliderCommit}
                max={180}
                step={0.01}
                className="w-full"
                disabled={isSending}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0°</span>
                <span>180°</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">SERVO 4 - WRIST PITCH</span>
                <span className="data-value text-lg">{wristPitch[0].toFixed(2)}°</span>
              </div>
              <Slider
                value={wristPitch}
                onValueChange={handleSliderChange(setWristPitch)}
                onValueCommit={handleSliderCommit}
                max={180}
                step={0.01}
                className="w-full"
                disabled={isSending}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0°</span>
                <span>180°</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">SERVO 5 - WRIST ROLL</span>
                <span className="data-value text-lg">{wristRoll[0].toFixed(2)}°</span>
              </div>
              <Slider
                value={wristRoll}
                onValueChange={handleSliderChange(setWristRoll)}
                onValueCommit={handleSliderCommit}
                max={180}
                step={0.01}
                className="w-full"
                disabled={isSending}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0°</span>
                <span>180°</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">SERVO 6 - GRIPPER</span>
                <span className="data-value text-lg">{gripper[0].toFixed(2)}°</span>
              </div>
              <Slider
                value={gripper}
                onValueChange={handleSliderChange(setGripper)}
                onValueCommit={handleSliderCommit}
                max={180}
                step={0.01}
                className="w-full"
                disabled={isSending}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>CLOSED</span>
                <span>OPEN</span>
              </div>
            </div>

            {/* Speed Controller */}
            <div className="space-y-2 pt-4 border-t border-border">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">MOVEMENT SPEED</span>
                <span className="data-value text-lg">{speed[0].toFixed(0)} ms</span>
              </div>
              <Slider
                value={speed}
                onValueChange={setSpeed}
                min={100}
                max={3000}
                step={50}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>FAST (100ms)</span>
                <span>SLOW (3000ms)</span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="space-y-3 pt-4 border-t border-border">
              <Button
                onClick={handleSavePosition}
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
                size="lg"
              >
                <Save className="h-4 w-4 mr-2" />
                SAVE POSITION ({savedPositions.length})
              </Button>

              <div className="grid grid-cols-2 gap-3">
                <Button
                  onClick={handlePlayMovements}
                  disabled={isPlaying || savedPositions.length === 0}
                  className="bg-status-active text-foreground hover:bg-status-active/90"
                  size="lg"
                >
                  <Play className="h-4 w-4 mr-2" />
                  PLAY
                </Button>

                <Button
                  onClick={handleStopMovement}
                  disabled={!isPlaying}
                  className="bg-critical text-critical-foreground hover:bg-critical/90"
                  size="lg"
                >
                  <StopCircle className="h-4 w-4 mr-2" />
                  STOP
                </Button>
              </div>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};

export default ManualControls;
