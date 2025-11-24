import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Terminal } from "lucide-react";

interface LogEntry {
  timestamp: string;
  type: "SYSTEM" | "AI" | "IK" | "SERVO" | "ERROR";
  message: string;
}

const SystemLogs = () => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      timestamp: new Date().toLocaleTimeString(),
      type: "SYSTEM",
      message: "Initializing Vision System...",
    },
    {
      timestamp: new Date().toLocaleTimeString(),
      type: "SYSTEM",
      message: "Servo controllers connected: 4/4",
    },
    {
      timestamp: new Date().toLocaleTimeString(),
      type: "AI",
      message: "Target Identified: Red Cube at (10, 5, 0)",
    },
    {
      timestamp: new Date().toLocaleTimeString(),
      type: "IK",
      message: "Solution Found: B:45° S:60° E:110°",
    },
    {
      timestamp: new Date().toLocaleTimeString(),
      type: "SERVO",
      message: "Motion sequence completed successfully",
    },
  ]);

  useEffect(() => {
    // Simulate periodic log updates
    const interval = setInterval(() => {
      const randomLogs = [
        { type: "SYSTEM" as const, message: "Heartbeat: All systems nominal" },
        { type: "AI" as const, message: "Object tracking: Maintaining lock on target" },
        { type: "IK" as const, message: "Path planning: Trajectory optimized" },
        { type: "SERVO" as const, message: "Position feedback: ±0.2° tolerance" },
      ];
      
      const randomLog = randomLogs[Math.floor(Math.random() * randomLogs.length)];
      
      setLogs(prev => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString(),
          ...randomLog,
        },
      ].slice(-20)); // Keep last 20 logs
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const getLogColor = (type: string) => {
    switch (type) {
      case "SYSTEM":
        return "text-primary";
      case "AI":
        return "text-status-active";
      case "IK":
        return "text-warning";
      case "SERVO":
        return "text-blue-400";
      case "ERROR":
        return "text-critical";
      default:
        return "text-foreground";
    }
  };

  return (
    <Card className="bg-terminal-bg border-border">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm data-label flex items-center gap-2">
          <Terminal className="h-4 w-4 text-terminal-text" />
          SYSTEM LOGS
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-32" ref={scrollRef}>
          <div className="space-y-1 font-mono text-xs">
            {logs.map((log, idx) => (
              <div key={idx} className="flex gap-2">
                <span className="text-muted-foreground">[{log.timestamp}]</span>
                <span className={getLogColor(log.type)}>[{log.type}]</span>
                <span className="text-terminal-text">{log.message}</span>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default SystemLogs;
