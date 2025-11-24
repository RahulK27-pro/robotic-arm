import { Camera } from "lucide-react";
import { Card } from "@/components/ui/card";

const CameraView = () => {
  return (
    <Card className="relative overflow-hidden bg-muted border-border">
      <div className="aspect-video w-full bg-gradient-to-br from-muted via-card to-muted flex items-center justify-center relative">
        {/* Camera Feed Placeholder */}
        {/* Live Camera Feed */}
        <img
          src="http://localhost:5000/video_feed"
          alt="Live Camera Feed"
          className="absolute inset-0 w-full h-full object-cover"
        />

        {/* Crosshair Overlay */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          {/* Vertical line */}
          <line
            x1="50" y1="0"
            x2="50" y2="100"
            stroke="hsl(var(--primary))"
            strokeWidth="0.1"
            opacity="0.3"
          />
          {/* Horizontal line */}
          <line
            x1="0" y1="50"
            x2="100" y2="50"
            stroke="hsl(var(--primary))"
            strokeWidth="0.1"
            opacity="0.3"
          />

          {/* Grid lines */}
          {[25, 75].map(pos => (
            <g key={pos}>
              <line
                x1={pos} y1="0"
                x2={pos} y2="100"
                stroke="hsl(var(--border))"
                strokeWidth="0.05"
                opacity="0.2"
              />
              <line
                x1="0" y1={pos}
                x2="100" y2={pos}
                stroke="hsl(var(--border))"
                strokeWidth="0.05"
                opacity="0.2"
              />
            </g>
          ))}

          {/* Center crosshair */}
          <circle
            cx="50" cy="50" r="3"
            fill="none"
            stroke="hsl(var(--primary))"
            strokeWidth="0.2"
          />
          <circle
            cx="50" cy="50" r="1"
            fill="hsl(var(--primary))"
            opacity="0.5"
          />
        </svg>

        {/* Status overlay */}
        <div className="absolute top-2 left-2 bg-background/80 backdrop-blur-sm px-3 py-1 rounded text-xs">
          <span className="data-label">CAM-01</span>
          <span className="ml-2 text-status-active">● LIVE</span>
        </div>

        <div className="absolute top-2 right-2 bg-background/80 backdrop-blur-sm px-3 py-1 rounded text-xs data-label">
          1920×1080 | 30 FPS
        </div>
      </div>
    </Card>
  );
};

export default CameraView;
