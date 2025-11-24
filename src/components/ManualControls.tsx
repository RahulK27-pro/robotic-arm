import { useState } from "react";
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

const ManualControls = () => {
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

  const handlePlayMovements = () => {
    if (savedPositions.length === 0) {
      toast.error("No saved positions", {
        description: "Save at least one position first",
      });
      return;
    }
    setIsPlaying(true);
    toast.info("Playing movements", {
      description: `${savedPositions.length} positions queued`,
    });
    // Simulate playback
    setTimeout(() => setIsPlaying(false), 3000);
  };

  const handleStopMovement = () => {
    setIsPlaying(false);
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
            </CardTitle>
            <ChevronDown
              className={`h-4 w-4 transition-transform ${
                isOpen ? "rotate-180" : ""
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
                onValueChange={setBase}
                max={180}
                step={0.01}
                className="w-full"
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
                onValueChange={setShoulder}
                max={180}
                step={0.01}
                className="w-full"
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
                onValueChange={setElbow}
                max={180}
                step={0.01}
                className="w-full"
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
                onValueChange={setWristPitch}
                max={180}
                step={0.01}
                className="w-full"
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
                onValueChange={setWristRoll}
                max={180}
                step={0.01}
                className="w-full"
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
                onValueChange={setGripper}
                max={180}
                step={0.01}
                className="w-full"
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
