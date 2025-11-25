import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Loader2, Bot, User } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const AICommandCenter = () => {
  const [command, setCommand] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "AI Command Center initialized. Type colors to search (e.g., 'Find Red and Green').",
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const addMessage = (role: "user" | "assistant", content: string) => {
    setMessages(prev => [...prev, {
      role,
      content,
      timestamp: new Date().toLocaleTimeString()
    }]);
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setLoading(false);
  };

  const startPolling = (targetColors: string[]) => {
    let attempts = 0;
    const maxAttempts = 20;

    pollIntervalRef.current = setInterval(async () => {
      attempts++;
      try {
        const response = await fetch("http://localhost:5000/get_detection_result");
        const data = await response.json();

        if (data.status === "found" && data.data && data.data.length > 0) {
          // Group detections by color
          const groupedByColor: { [key: string]: any[] } = {};

          data.data.forEach((detection: any) => {
            if (targetColors.includes(detection.color)) {
              if (!groupedByColor[detection.color]) {
                groupedByColor[detection.color] = [];
              }
              groupedByColor[detection.color].push(detection);
            }
          });

          const foundColors = Object.keys(groupedByColor);

          if (foundColors.length > 0) {
            // Build message
            const colorMessages = foundColors.map(color => {
              const instances = groupedByColor[color];
              const coords = instances.map(d => `(${d.x}, ${d.y})`).join(", ");
              return `${color}: ${instances.length} object${instances.length > 1 ? 's' : ''} at ${coords}`;
            });

            const message = `Target${foundColors.length > 1 ? 's' : ''} Acquired:\n${colorMessages.join('\n')}`;
            addMessage("assistant", message);
            stopPolling();
          }
        } else if (attempts >= maxAttempts) {
          addMessage("assistant", `Timeout: Could not find ${targetColors.join(' and ')} within 10 seconds.`);
          stopPolling();
        }
      } catch (error) {
        console.error("Polling error:", error);
      }
    }, 500);
  };

  const handleSendCommand = async () => {
    if (!command.trim()) return;

    const userText = command.trim();
    addMessage("user", userText);
    setCommand("");
    setLoading(true);

    // Parse multiple colors from input
    const availableColors = ["Red", "Blue", "Green", "Yellow"];
    const targetColors = availableColors.filter(c =>
      userText.toLowerCase().includes(c.toLowerCase())
    );

    if (targetColors.length === 0) {
      setTimeout(() => {
        addMessage("assistant", "I didn't understand the color(s). Please specify Red, Blue, Green, or Yellow.");
        setLoading(false);
      }, 500);
      return;
    }

    try {
      await fetch("http://localhost:5000/set_target_color", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ colors: targetColors }),
      });

      const colorList = targetColors.join(" and ");
      addMessage("assistant", `Scanning for ${colorList}...`);
      startPolling(targetColors);

    } catch (error) {
      addMessage("assistant", "Error: Could not connect to backend.");
      setLoading(false);
    }
  };

  useEffect(() => {
    return () => stopPolling();
  }, []);

  return (
    <Card className="bg-card border-border h-full flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm data-label flex items-center gap-2">
          <Bot className="h-4 w-4 text-primary" />
          AI COMMAND CENTER
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-4 p-4">
        <ScrollArea className="flex-1 pr-4">
          <div className="space-y-4">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
              >
                {msg.role === "assistant" && (
                  <div className="flex-shrink-0 w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded p-3 ${msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                    }`}
                >
                  <div className="text-sm whitespace-pre-line">{msg.content}</div>
                  <div className="text-xs opacity-60 mt-1">{msg.timestamp}</div>
                </div>
                {msg.role === "user" && (
                  <div className="flex-shrink-0 w-8 h-8 rounded bg-secondary flex items-center justify-center">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex gap-3 justify-start">
                <div className="flex-shrink-0 w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-muted rounded p-3">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="flex gap-2">
          <Input
            placeholder="Type 'Find Red and Green'..."
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSendCommand()}
            className="bg-muted border-border font-mono text-sm"
            disabled={loading}
          />
          <Button
            onClick={handleSendCommand}
            disabled={loading || !command.trim()}
            className="bg-primary hover:bg-primary/90"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default AICommandCenter;
