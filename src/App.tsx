import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import MimicPage from "./pages/MimicPage";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

import { StatusProvider } from "@/context/StatusContext";
import { LogProvider } from "@/context/LogContext";

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <StatusProvider>
        <LogProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/mimic" element={<MimicPage />} />
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </LogProvider>
      </StatusProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
