import React, { createContext, useContext, useState, useEffect } from "react";

interface StatusContextType {
    backend: "connected" | "disconnected";
    vision: "active" | "inactive";
    servo: "on" | "off";
}

const StatusContext = createContext<StatusContextType>({
    backend: "disconnected",
    vision: "inactive",
    servo: "off",
});

export const useStatus = () => useContext(StatusContext);

export const StatusProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [status, setStatus] = useState<StatusContextType>({
        backend: "disconnected",
        vision: "inactive",
        servo: "off",
    });

    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const response = await fetch("http://localhost:5000/status");
                if (response.ok) {
                    const data = await response.json();
                    setStatus({
                        backend: "connected",
                        vision: data.vision,
                        servo: data.servo,
                    });
                } else {
                    setStatus({
                        backend: "disconnected",
                        vision: "inactive",
                        servo: "off",
                    });
                }
            } catch (error) {
                setStatus({
                    backend: "disconnected",
                    vision: "inactive",
                    servo: "off",
                });
            }
        };

        // Initial fetch
        fetchStatus();

        // Poll every 2 seconds
        const interval = setInterval(fetchStatus, 2000);

        return () => clearInterval(interval);
    }, []);

    return (
        <StatusContext.Provider value={status}>
            {children}
        </StatusContext.Provider>
    );
};
