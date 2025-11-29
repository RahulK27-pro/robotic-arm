import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity } from "lucide-react";

interface ServoPositionPanelProps {
    angles: number[];
}

const ServoPositionPanel = ({ angles = [0, 0, 0, 0, 0, 0] }: ServoPositionPanelProps) => {
    const servoLabels = [
        "Base",
        "Shoulder",
        "Elbow",
        "Wrist Pitch",
        "Wrist Roll",
        "Gripper"
    ];

    return (
        <Card className="bg-card border-border">
            <CardHeader className="pb-3">
                <CardTitle className="text-sm data-label flex items-center gap-2">
                    <Activity className="h-4 w-4 text-primary" />
                    SERVO POSITIONS
                </CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
                {servoLabels.map((label, idx) => (
                    <div key={idx} className="space-y-1">
                        <div className="flex justify-between items-center">
                            <span className="text-xs font-mono text-muted-foreground">
                                {label}
                            </span>
                            <span className="text-sm font-mono font-bold text-primary">
                                {angles[idx]?.toFixed(2) || "0.00"}°
                            </span>
                        </div>
                        <div className="relative h-2 bg-muted rounded-full overflow-hidden">
                            <div
                                className="absolute h-full bg-gradient-to-r from-primary/50 to-primary transition-all duration-300"
                                style={{
                                    width: `${Math.min(Math.abs(angles[idx] || 0) / 180 * 100, 100)}%`
                                }}
                            />
                        </div>
                    </div>
                ))}
            </CardContent>
        </Card>
    );
};

export default ServoPositionPanel;
