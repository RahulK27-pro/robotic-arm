import { useEffect, useRef } from "react";
import { useLogs } from "@/context/LogContext";
import { useStatus } from "@/context/StatusContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Terminal } from "lucide-react";



const SystemLogs = () => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { logs, addLog } = useLogs();
  const { backend } = useStatus();

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  // Heartbeat logger
  useEffect(() => {
    const interval = setInterval(() => {
      if (backend === "connected") {
        addLog("SYSTEM", "Heartbeat: All systems nominal");
      }
    }, 10000); // Log every 10 seconds

    return () => clearInterval(interval);
  }, [backend, addLog]);



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
