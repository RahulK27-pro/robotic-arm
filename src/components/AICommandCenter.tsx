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

  // Polling removed as we now get immediate response from /command
  // Keeping the ref cleanup for safety
  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setLoading(false);
  };

  const handleSendCommand = async () => {
    if (!command.trim()) return;

    const userText = command.trim();
    addMessage("user", userText);
    setCommand("");
    setLoading(true);

    try {
      // First, get the current vision state
      const visionResponse = await fetch("http://localhost:5000/get_detection_result");
      const visionData = await visionResponse.json();

      // Format vision state
      let visionState: { [key: string]: [number, number] } = {};
      if (visionData.status === "found" && visionData.data) {
        visionData.data.forEach((obj: any) => {
          const key = `${obj.color.toLowerCase()}_cube`;
          visionState[key] = [obj.x, obj.y];
        });
      }

      // Send command to AI
      const response = await fetch("http://localhost:5000/process_command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: userText }),
      });

      const data = await response.json();

      // Build detailed response message
      let detailedMessage = "";

      // Add Vision State
      detailedMessage += `Vision State: ${JSON.stringify(visionState)}\n\n`;

      // Add Response
      detailedMessage += "--- Response ---\n";
      detailedMessage += JSON.stringify({ plan: data.plan || [], reply: data.reply || "" }, null, 2);

      // Add status
      if (data.plan && data.plan.length > 0) {
        detailedMessage += "\n\n[SUCCESS] Plan generated successfully.";
      }

      if (data.reply || data.plan) {
        addMessage("assistant", detailedMessage);
      } else if (data.error) {
        addMessage("assistant", `Error: ${data.error}`);
      } else {
        addMessage("assistant", "Received an empty response from the Brain.");
      }

    } catch (error) {
      addMessage("assistant", "Error: Could not connect to backend.");
      console.error(error);
    } finally {
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
