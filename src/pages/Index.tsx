import { useState, useEffect } from "react";
import Header from "@/components/Header";
import CameraView from "@/components/CameraView";
import Telemetry from "@/components/Telemetry";
import AICommandCenter from "@/components/AICommandCenter";
import ManualControls from "@/components/ManualControls";
import SystemLogs from "@/components/SystemLogs";
import { Hand, Activity } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";

const Index = () => {
    const [liveMode, setLiveMode] = useState(false);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        checkLiveStatus();
    }, []);

    const checkLiveStatus = async () => {
        try {
            const res = await fetch("http://localhost:5000/live/status");
            const data = await res.json();
            setLiveMode(data.active);
        } catch (error) {
            console.error("Failed to check live status", error);
        }
    };

    const toggleLiveMode = async () => {
        setLoading(true);
        try {
            const endpoint = liveMode ? "stop" : "start";
            const res = await fetch(`http://localhost:5000/live/${endpoint}`, { method: "POST" });
            const data = await res.json();

            if (data.status === "started") {
                setLiveMode(true);
                toast({
                    title: "Live Mode Activated",
                    description: "The robot is now alive!",
                    className: "bg-emerald-900 border-emerald-500 text-emerald-100",
                });
            } else {
                setLiveMode(false);
                toast({
                    title: "Live Mode Deactivated",
                    description: "The robot is resting.",
                });
            }
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to toggle Live Mode",
                variant: "destructive",
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-background flex flex-col">
            <Header />

            <main className="flex-1 p-6">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
                    {/* Left Panel: Vision & Telemetry */}
                    <div className="lg:col-span-2 space-y-6">
                        <CameraView />
                        <Telemetry />

                        <div className="flex gap-4">
                            {/* Mimic Mode Tile */}
                            <a
                                href="/mimic"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block group flex-1"
                            >
                                <Card className="bg-slate-900 border-slate-700 hover:border-cyan-400 transition-all duration-300 hover:shadow-lg hover:shadow-cyan-400/20 cursor-pointer h-full">
                                    <CardContent className="p-8 flex flex-col items-center justify-center text-center gap-4 min-h-[160px]">
                                        <Hand className="w-12 h-12 text-slate-500 group-hover:text-cyan-400 transition-colors duration-300" />
                                        <div>
                                            <h3 className="text-lg font-bold text-slate-200 uppercase leading-tight mb-1">
                                                MIMIC MODE
                                            </h3>
                                            <p className="text-xs font-mono text-slate-500">
                                                Visual Hand Tracking
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                            </a>

                            {/* Live Mode Tile */}
                            <div className="flex-1" onClick={toggleLiveMode}>
                                <Card className={`border-slate-700 transition-all duration-300 cursor-pointer h-full hover:shadow-lg ${liveMode ? "bg-emerald-950 border-emerald-500 shadow-emerald-500/20" : "bg-slate-900 hover:border-emerald-400 hover:shadow-emerald-400/20"}`}>
                                    <CardContent className="p-8 flex flex-col items-center justify-center text-center gap-4 min-h-[160px]">
                                        <Activity className={`w-12 h-12 transition-all duration-500 ${liveMode ? "text-emerald-400 animate-pulse" : "text-slate-500"}`} />
                                        <div>
                                            <h3 className={`text-lg font-bold uppercase leading-tight mb-1 ${liveMode ? "text-emerald-100" : "text-slate-200"}`}>
                                                {liveMode ? "ALIVE" : "LIVE MODE"}
                                            </h3>
                                            <p className={`text-xs font-mono ${liveMode ? "text-emerald-400" : "text-slate-500"}`}>
                                                {liveMode ? "Autonomous Behavior Active" : "Click to Wake Up"}
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
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
