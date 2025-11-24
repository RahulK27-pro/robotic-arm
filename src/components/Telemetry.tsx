import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const Telemetry = () => {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm data-label">LIVE COORDINATES</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-1">
            <div className="data-label text-xs">X-AXIS</div>
            <div className="data-value text-3xl">142.5</div>
            <div className="text-xs text-muted-foreground">mm</div>
          </div>
          
          <div className="space-y-1">
            <div className="data-label text-xs">Y-AXIS</div>
            <div className="data-value text-3xl">87.3</div>
            <div className="text-xs text-muted-foreground">mm</div>
          </div>
          
          <div className="space-y-1">
            <div className="data-label text-xs">Z-AXIS</div>
            <div className="data-value text-3xl">203.8</div>
            <div className="text-xs text-muted-foreground">mm</div>
          </div>
        </div>
        
        <div className="pt-2 border-t border-border flex items-center justify-between">
          <span className="data-label text-xs">GRIPPER STATE</span>
          <Badge variant="outline" className="bg-status-active/10 text-status-active border-status-active">
            OPEN
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
};

export default Telemetry;
