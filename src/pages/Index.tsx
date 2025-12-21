import Header from "@/components/Header";
import CameraView from "@/components/CameraView";
import Telemetry from "@/components/Telemetry";
import AICommandCenter from "@/components/AICommandCenter";
import ManualControls from "@/components/ManualControls";
import SystemLogs from "@/components/SystemLogs";
import { Hand } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

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

                        {/* Mimic Mode Tile - Square with Vertical Layout */}
                        <a
                            href="/mimic"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block group w-full max-w-xs"
                        >
                            <Card className="bg-slate-900 border-slate-700 hover:border-cyan-400 transition-all duration-300 hover:shadow-lg hover:shadow-cyan-400/20 cursor-pointer">
                                <CardContent className="p-8 flex flex-col items-center justify-center text-center gap-4 min-h-[200px]">
                                    <Hand className="w-16 h-16 text-slate-500 group-hover:text-cyan-400 transition-colors duration-300" />
                                    <div>
                                        <h3 className="text-xl font-bold text-slate-200 uppercase leading-tight mb-1">
                                            MIMIC MODE
                                        </h3>
                                        <p className="text-xs font-mono text-slate-500">
                                            Visual Hand Tracking
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        </a>
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
