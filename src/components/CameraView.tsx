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
