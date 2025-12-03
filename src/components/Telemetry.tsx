import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface CoordinateData {
  x: number;
  y: number;
  z: number;
}

const API_BASE = "http://localhost:5000";

const Telemetry = () => {
  const [coordinates, setCoordinates] = useState<CoordinateData>({ x: 0, y: 0, z: 0 });
  const [gripperState, setGripperState] = useState<string>("OPEN");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // Connect to SSE stream for real-time updates
    const eventSource = new EventSource(`${API_BASE}/servo_stream`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setConnected(true);

        // Update coordinates from stream
        if (data.coordinates) {
          setCoordinates({
            x: data.coordinates.x,
            y: data.coordinates.y,
            z: data.coordinates.z,
          });
        }

        // Update gripper state
        if (data.gripper_state) {
          setGripperState(data.gripper_state);
        }
      } catch (error) {
        console.error("Error parsing telemetry data:", error);
      }
    };

    eventSource.onerror = (error) => {
      console.error("SSE Connection Error:", error);
      setConnected(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, []);

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm data-label flex items-center justify-between">
          LIVE COORDINATES
          <span className={`text-xs ${connected ? "text-status-active" : "text-critical"}`}>
            {connected ? "🟢 LIVE" : "🔴 OFFLINE"}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
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
          <span className="data-label text-xs">GRIPPER STATE</span>
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
      </CardContent>
    </Card>
  );
};

export default Telemetry;
