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

            {/* Mimic Mode Button */}
            <div className="bg-gradient-to-br from-purple-900/20 to-blue-900/20 border border-purple-500/30 rounded-lg p-4 hover:border-purple-400/50 transition-all">
              <h3 className="text-lg font-bold mb-2 text-purple-300">🤖 Mimic Mode</h3>
              <p className="text-sm text-muted-foreground mb-3">
                Control the arm with hand gestures via webcam teleoperation.
              </p>
              <a
                href="/mimic"
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-bold py-3 px-4 rounded-lg text-center transition-all transform hover:scale-105 active:scale-95 shadow-lg"
              >
                Open Mimic Control
              </a>
            </div>
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
