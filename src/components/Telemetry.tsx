import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Brain, Target, ArrowLeftRight, Ruler } from "lucide-react";

interface CoordinateData {
    x: number;
    y: number;
    z: number;
}

interface ServoingTelemetry {
    mode: string;
    active_brain: string;
    correction_x: number;
    distance: number;
}

const API_BASE = "http://localhost:5000";

const Telemetry = () => {
    const [coordinates, setCoordinates] = useState<CoordinateData>({ x: 0, y: 0, z: 0 });
    const [gripperState, setGripperState] = useState<string>("OPEN");
    const [connected, setConnected] = useState(false);

    // ANFIS State
    const [servoingActive, setServoingActive] = useState(false);
    const [anfisStats, setAnfisStats] = useState<ServoingTelemetry>({
        mode: "IDLE",
        active_brain: "None",
        correction_x: 0,
        distance: 0
    });

    useEffect(() => {
        // 1. SSE Stream (Hardware/Sim Data)
        const eventSource = new EventSource(`${API_BASE}/servo_stream`);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setConnected(true);

                if (data.coordinates) {
                    setCoordinates({
                        x: data.coordinates.x,
                        y: data.coordinates.y,
                        z: data.coordinates.z,
                    });
                }
                if (data.gripper_state) {
                    setGripperState(data.gripper_state);
                }
            } catch (error) {
                console.error("Error parsing telemetry data:", error);
            }
        };

        eventSource.onerror = () => {
            setConnected(false);
        };

        // 2. Poll Servoing Status (Brain Data)
        const pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/servoing_status`);
                const data = await res.json();
                if (data) {
                    setServoingActive(data.active);
                    if (data.telemetry) {
                        setAnfisStats(data.telemetry);
                    }
                }
            } catch (e) {
                // Silent fail
            }
        }, 200);

        return () => {
            eventSource.close();
            clearInterval(pollInterval);
        };
    }, []);

    return (
        <Card className="bg-card border-border">
            <CardHeader className="pb-3">
                <CardTitle className="text-sm data-label flex items-center justify-between">
                    LIVE TELEMETRY
                    <span className={`text-xs ${connected ? "text-status-active" : "text-critical"}`}>
                        {connected ? "🟢 LIVE" : "🔴 OFFLINE"}
                    </span>
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Hardware Coordinates */}
                <div className="grid grid-cols-3 gap-4">
                    <div className="space-y-1">
                        <div className="data-label text-xs">X-AXIS</div>
                        <div className="data-value text-3xl">{coordinates.x.toFixed(1)}</div>
                        <div className="text-xs text-muted-foreground">mm</div>
                    </div>

                    <div className="space-y-1">
                        <div className="data-label text-xs">Y-AXIS</div>
                        <div className="data-value text-3xl">{coordinates.y.toFixed(1)}</div>
                        <div className="text-xs text-muted-foreground">mm</div>
                    </div>

                    <div className="space-y-1">
                        <div className="data-label text-xs">Z-AXIS</div>
                        <div className="data-value text-3xl">{coordinates.z.toFixed(1)}</div>
                        <div className="text-xs text-muted-foreground">mm</div>
                    </div>
                </div>

                <div className="pt-2 border-t border-border flex items-center justify-between">
                    <span className="data-label text-xs">GRIPPER</span>
                    <Badge
                        variant="outline"
                        className={
                            gripperState === "OPEN"
                                ? "bg-status-active/10 text-status-active border-status-active"
                                : "bg-critical/10 text-critical border-critical"
                        }
                    >
                        {gripperState}
                    </Badge>
                </div>

                {/* ANFIS Brain Status */}
                <div className="pt-4 border-t border-border space-y-3">
                    <div className="flex items-center justify-between mb-2">
                        <div className="text-sm font-semibold flex items-center gap-2">
                            <Brain className="w-4 h-4 text-primary" />
                            ANFIS BRAIN
                        </div>
                        {servoingActive && (
                            <Badge variant="secondary" className="animate-pulse bg-primary/20 text-primary">
                                ACTIVE
                            </Badge>
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-muted/50 p-2 rounded">
                            <div className="text-muted-foreground mb-1">MODE</div>
                            <div className="font-mono font-bold text-primary">{anfisStats.mode}</div>
                        </div>
                        <div className="bg-muted/50 p-2 rounded">
                            <div className="text-muted-foreground mb-1">ACTIVE NET</div>
                            <div className="font-mono">{anfisStats.active_brain}</div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-muted/50 p-2 rounded">
                            <div className="text-muted-foreground mb-1 flex items-center gap-1">
                                <ArrowLeftRight className="w-3 h-3" /> CORR X
                            </div>
                            <div className="font-mono">{anfisStats.correction_x.toFixed(2)}°</div>
                        </div>
                        <div className="bg-muted/50 p-2 rounded">
                            <div className="text-muted-foreground mb-1 flex items-center gap-1">
                                <Ruler className="w-3 h-3" /> DIST
                            </div>
                            <div className="font-mono">{anfisStats.distance.toFixed(1)} cm</div>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default Telemetry;
