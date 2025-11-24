import Header from "@/components/Header";
import CameraView from "@/components/CameraView";
import Telemetry from "@/components/Telemetry";
import AICommandCenter from "@/components/AICommandCenter";
import ManualControls from "@/components/ManualControls";
import SystemLogs from "@/components/SystemLogs";

const Index = () => {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      
      <main className="flex-1 p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
          {/* Left Panel: Vision & Telemetry */}
          <div className="lg:col-span-2 space-y-6">
            <CameraView />
            <Telemetry />
          </div>
          
          {/* Right Panel: Control Logic */}
          <div className="space-y-6 flex flex-col">
            <div className="flex-1">
              <AICommandCenter />
            </div>
            <ManualControls />
          </div>
        </div>
      </main>
      
      {/* Footer: System Logs */}
      <footer className="p-6 pt-0">
        <SystemLogs />
      </footer>
    </div>
  );
};

export default Index;
