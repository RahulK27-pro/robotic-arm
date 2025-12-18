import React, { createContext, useContext, useState, useCallback } from "react";

export type LogType = "SYSTEM" | "AI" | "IK" | "SERVO" | "ERROR" | "AUTO";

export interface LogEntry {
    timestamp: string;
    type: LogType;
    message: string;
}

interface LogContextType {
    logs: LogEntry[];
    addLog: (type: LogType, message: string) => void;
    clearLogs: () => void;
}

const LogContext = createContext<LogContextType>({
    logs: [],
    addLog: () => { },
    clearLogs: () => { },
});

export const useLogs = () => useContext(LogContext);

export const LogProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [logs, setLogs] = useState<LogEntry[]>([]);

    const addLog = useCallback((type: LogType, message: string) => {
        setLogs((prev) => {
            const newLog: LogEntry = {
                timestamp: new Date().toLocaleTimeString(),
                type,
                message,
            };
            // Keep only the last 50 logs to prevent performance issues
            return [...prev, newLog].slice(-50);
        });
    }, []);

    const clearLogs = useCallback(() => {
        setLogs([]);
    }, []);

    return (
        <LogContext.Provider value={{ logs, addLog, clearLogs }}>
            {children}
        </LogContext.Provider>
    );
};
