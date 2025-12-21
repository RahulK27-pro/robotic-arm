import React, { useState, useEffect } from 'react';
import Header from "@/components/Header";
import { Hand, Camera, MousePointer2, Activity } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const MimicPage = () => {
    const [active, setActive] = useState(false);
    const [loading, setLoading] = useState(false);
    const [telemetry, setTelemetry] = useState({
        error_x: 0,
        error_y: 0,
        reach: 0,
        gripper: "OPEN",
        is_centered: false
    });

    const toggleMimic = async () => {
        setLoading(true);
        const endpoint = active ? 'http://localhost:5000/mimic_stop' : 'http://localhost:5000/mimic_start';

        try {
            const res = await fetch(endpoint, { method: 'POST' });
            const data = await res.json();

            if (data.status === "started") setActive(true);
            if (data.status === "stopped") setActive(false);
            if (data.status === "already_running") setActive(true);

        } catch (err) {
            console.error("Failed to toggle Mimic Mode:", err);
        } finally {
            setLoading(false);
        }
    };

    // Poll telemetry when active
    useEffect(() => {
        if (!active) return;

        const interval = setInterval(async () => {
            try {
                const res = await fetch('http://localhost:5000/mimic_telemetry');
                const data = await res.json();
                setTelemetry(data);
            } catch (err) {
                console.error("Failed to fetch telemetry:", err);
            }
        }, 100); // Update 10 times per second

        return () => clearInterval(interval);
    }, [active]);

    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col">
            <Header />

            <main className="flex-1 p-6">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left: Camera Feed (takes 2 columns) */}
                    <div className="lg:col-span-2 space-y-4">
                        <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
                            <CardHeader className="pb-3">
                                <CardTitle className="flex items-center gap-2">
                                    <Activity className="w-5 h-5 text-primary" />
                                    Live Camera Feed
                                    {active && (
                                        <span className="ml-auto flex items-center gap-2 text-sm text-green-400">
                                            <span className="relative flex h-2 w-2">
                                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                                            </span>
                                            Hand Tracking Active
                                        </span>
                                    )}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="relative aspect-video bg-black rounded-lg overflow-hidden border border-border/50">
                                    <img
                                        src="http://localhost:5000/mimic_video_feed"
                                        alt="Camera Feed"
                                        className="w-full h-full object-contain"
                                    />
                                    {!active && (
                                        <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                                            <div className="text-center">
                                                <Camera className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
                                                <p className="text-muted-foreground">Click "Activate" to start hand tracking</p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>

                        {/* Telemetry Display */}
                        {active && (
                            <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-lg">📊 Live Telemetry</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        {/* Error X */}
                                        <div className="space-y-1">
                                            <div className="text-xs text-muted-foreground">X Offset</div>
                                            <div className={`text-2xl font-bold font-mono ${Math.abs(telemetry.error_x) <= 50 ? 'text-green-400' : 'text-orange-400'}`}>
                                                {telemetry.error_x > 0 ? '+' : ''}{telemetry.error_x}
                                            </div>
                                            <div className="text-xs text-muted-foreground">pixels</div>
                                        </div>

                                        {/* Error Y */}
                                        <div className="space-y-1">
                                            <div className="text-xs text-muted-foreground">Y Offset</div>
                                            <div className={`text-2xl font-bold font-mono ${Math.abs(telemetry.error_y) <= 50 ? 'text-green-400' : 'text-orange-400'}`}>
                                                {telemetry.error_y > 0 ? '+' : ''}{telemetry.error_y}
                                            </div>
                                            <div className="text-xs text-muted-foreground">pixels</div>
                                        </div>

                                        {/* Reach */}
                                        <div className="space-y-1">
                                            <div className="text-xs text-muted-foreground">Reach</div>
                                            <div className="text-2xl font-bold font-mono text-blue-400">
                                                {telemetry.reach}
                                            </div>
                                            <div className="text-xs text-muted-foreground">cm</div>
                                        </div>

                                        {/* Gripper */}
                                        <div className="space-y-1">
                                            <div className="text-xs text-muted-foreground">Gripper</div>
                                            <div className={`text-2xl font-bold ${telemetry.gripper === 'CLOSED' ? 'text-yellow-400' : 'text-gray-400'}`}>
                                                {telemetry.gripper === 'CLOSED' ? '🤏' : '✋'}
                                            </div>
                                            <div className="text-xs text-muted-foreground">{telemetry.gripper}</div>
                                        </div>
                                    </div>

                                    {/* Centered Status */}
                                    {telemetry.is_centered && (
                                        <div className="mt-4 p-2 bg-green-500/10 border border-green-500/30 rounded-lg text-center">
                                            <span className="text-green-400 font-semibold">✓ CENTERED</span>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        )}
                    </div>

                    {/* Right: Controls & Instructions */}
                    <div className="space-y-6">
                        {/* Control Card */}
                        <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-xl">
                                    🤖 Mimic Control
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
                                    <span className="text-sm font-medium">Status</span>
                                    <span className={`text-sm font-bold ${active ? 'text-green-400' : 'text-red-400'}`}>
                                        {active ? "ACTIVE" : "INACTIVE"}
                                    </span>
                                </div>

                                <div className="relative group">
                                    {active && (
                                        <div className="absolute -inset-1 bg-gradient-to-r from-red-600 to-orange-600 rounded-lg blur opacity-25 group-hover:opacity-50 transition duration-1000 group-hover:duration-200"></div>
                                    )}
                                    <Button
                                        onClick={toggleMimic}
                                        disabled={loading}
                                        size="lg"
                                        className={`relative w-full text-lg font-bold transition-all duration-300 transform hover:scale-105 active:scale-95 ${active
                                                ? 'bg-red-500 hover:bg-red-600 text-white'
                                                : 'bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-white'
                                            }`}
                                    >
                                        {loading ? (
                                            <span className="animate-spin mr-2">⏳</span>
                                        ) : active ? (
                                            "STOP MIMIC MODE"
                                        ) : (
                                            "ACTIVATE"
                                        )}
                                    </Button>
                                </div>

                                {active && (
                                    <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
                                        <p className="text-xs text-green-400 text-center font-mono">
                                            ● Tracking hand gestures...
                                        </p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Instructions Card */}
                        <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-lg">
                                    📋 How to Control
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3 text-sm">
                                <InstructionItem
                                    icon={<Hand className="w-5 h-5 text-blue-400" />}
                                    title="Position"
                                    desc="Robot tracks palm center - keep hand centered in frame"
                                />
                                <InstructionItem
                                    icon={<Camera className="w-5 h-5 text-purple-400" />}
                                    title="Reach"
                                    desc="Move hand closer to decrease reach, farther to increase"
                                />
                                <InstructionItem
                                    icon={<MousePointer2 className="w-5 h-5 text-green-400" />}
                                    title="Gripper"
                                    desc="Pinch thumb and index finger together to close gripper"
                                />

                                <div className="pt-3 border-t border-border/50">
                                    <p className="text-xs text-muted-foreground">
                                        <strong>Tip:</strong> Yellow crosshair shows frame center. Purple line shows centering error.
                                    </p>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </main>
        </div>
    );
};

const InstructionItem = ({ icon, title, desc }: { icon: any, title: string, desc: string }) => (
    <div className="flex items-start gap-3 p-3 bg-muted/20 rounded-lg border border-border/50">
        <div className="p-2 bg-background rounded-lg shadow-inner flex-shrink-0">
            {icon}
        </div>
        <div className="flex-1 min-w-0">
            <h4 className="font-semibold text-foreground mb-1">{title}</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>
        </div>
    </div>
);

export default MimicPage;
