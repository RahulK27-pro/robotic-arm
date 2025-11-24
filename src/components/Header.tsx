import { AlertCircle, Activity, Eye, Power } from "lucide-react";
import { Button } from "@/components/ui/button";

const Header = () => {
  return (
    <header className="border-b border-border bg-card px-6 py-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-wider text-primary">
          3-AXIS ARM CONTROLLER
        </h1>
        
        <div className="flex items-center gap-6">
          {/* Status Indicators */}
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-status-active" />
              <span className="data-label">Backend:</span>
              <span className="text-status-active font-semibold">Connected</span>
            </div>
            
            <div className="flex items-center gap-2">
              <Eye className="h-4 w-4 text-status-active" />
              <span className="data-label">Vision:</span>
              <span className="text-status-active font-semibold">Active</span>
            </div>
            
            <div className="flex items-center gap-2">
              <Power className="h-4 w-4 text-status-active" />
              <span className="data-label">Servo Power:</span>
              <span className="text-status-active font-semibold">ON</span>
            </div>
          </div>
          
          {/* Emergency Stop Button */}
          <Button 
            variant="destructive" 
            size="lg"
            className="bg-critical hover:bg-critical/90 text-critical-foreground font-bold tracking-wider shadow-lg shadow-critical/20"
          >
            <AlertCircle className="mr-2 h-5 w-5" />
            EMERGENCY STOP
          </Button>
        </div>
      </div>
    </header>
  );
};

export default Header;
