import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, Settings } from "lucide-react";

const ManualControls = () => {
  const [isOpen, setIsOpen] = useState(true);
  const [base, setBase] = useState([90]);
  const [shoulder, setShoulder] = useState([60]);
  const [elbow, setElbow] = useState([110]);
  const [gripper, setGripper] = useState([0.5]);

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
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">BASE ROTATION</span>
                <span className="data-value text-lg">{base[0]}°</span>
              </div>
              <Slider
                value={base}
                onValueChange={setBase}
                max={180}
                step={1}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0°</span>
                <span>180°</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">SHOULDER ANGLE</span>
                <span className="data-value text-lg">{shoulder[0]}°</span>
              </div>
              <Slider
                value={shoulder}
                onValueChange={setShoulder}
                max={180}
                step={1}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0°</span>
                <span>180°</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">ELBOW ANGLE</span>
                <span className="data-value text-lg">{elbow[0]}°</span>
              </div>
              <Slider
                value={elbow}
                onValueChange={setElbow}
                max={180}
                step={1}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0°</span>
                <span>180°</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="data-label text-xs">GRIPPER</span>
                <span className="data-value text-lg">{gripper[0].toFixed(2)}</span>
              </div>
              <Slider
                value={gripper}
                onValueChange={setGripper}
                max={1}
                step={0.01}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>CLOSED</span>
                <span>OPEN</span>
              </div>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};

export default ManualControls;
