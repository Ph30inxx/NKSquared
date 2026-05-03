import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AppBootstrap from "./components/AppBootstrap";
import ChatWidget from "./features/chatbot/ChatWidget";
import AppLayout from "./components/layout/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import ForexRatesPage from "./pages/admin/ForexRatesPage";
import MisDetailPage from "./pages/mis/MisDetailPage";
import MisInboxPage from "./pages/mis/MisInboxPage";
import ChatPage from "./features/chatbot/ChatPage";
import CompanyDetailPage from "./pages/portfolio/CompanyDetailPage";
import PortfolioGridPage from "./pages/portfolio/PortfolioGridPage";
import PortfolioListPage from "./pages/portfolio/PortfolioListPage";

export default function App() {
  return (
    <BrowserRouter>
      <AppBootstrap>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/portfolio" element={<PortfolioListPage />} />
              <Route path="/portfolio/:id" element={<CompanyDetailPage />} />
              <Route path="/grid" element={<PortfolioGridPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/mis" element={<MisInboxPage />} />
              <Route path="/mis/:id" element={<MisDetailPage />} />
              <Route path="/admin/forex-rates" element={<ForexRatesPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        {/* Chat widget — visible on all authenticated pages */}
        <ChatWidget />
      </AppBootstrap>
    </BrowserRouter>
  );
}
