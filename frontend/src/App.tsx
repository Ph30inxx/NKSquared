import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AppBootstrap from "./components/AppBootstrap";
import AppLayout from "./components/layout/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import AuditLogPage from "./pages/admin/AuditLogPage";
import ForexRatesPage from "./pages/admin/ForexRatesPage";
import RemindersPage from "./pages/admin/RemindersPage";
import MisDetailPage from "./pages/mis/MisDetailPage";
import MisInboxPage from "./pages/mis/MisInboxPage";
import MisTemplateBuilderPage from "./pages/mis/templates/MisTemplateBuilderPage";
import MisTemplateListPage from "./pages/mis/templates/MisTemplateListPage";
import ChatPage from "./features/chatbot/ChatPage";
import VoicePage from "./features/chatbot/VoicePage";
import CompanyDetailPage from "./pages/portfolio/CompanyDetailPage";
import PortfolioGridPage from "./pages/portfolio/PortfolioGridPage";
import PortfolioListPage from "./pages/portfolio/PortfolioListPage";
import PublicUploadPage from "./pages/public/PublicUploadPage";
import AIDashboardPage from "./pages/ai-dashboard/AIDashboardPage";

export default function App() {
  return (
    <BrowserRouter>
      <AppBootstrap>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/upload/:token" element={<PublicUploadPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/voice" element={<VoicePage />} />
            <Route element={<AppLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/ai-dashboard" element={<AIDashboardPage />} />
              <Route path="/portfolio" element={<PortfolioListPage />} />
              <Route path="/portfolio/:id" element={<CompanyDetailPage />} />
              <Route path="/grid" element={<PortfolioGridPage />} />
              <Route path="/mis" element={<MisInboxPage />} />
              <Route path="/mis/templates" element={<MisTemplateListPage />} />
              <Route path="/mis/templates/new" element={<MisTemplateBuilderPage />} />
              <Route path="/mis/templates/:id/edit" element={<MisTemplateBuilderPage />} />
              <Route path="/mis/:id" element={<MisDetailPage />} />
              <Route path="/admin/forex-rates" element={<ForexRatesPage />} />
              <Route path="/admin/reminders" element={<RemindersPage />} />
              <Route path="/admin/audit-log" element={<AuditLogPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppBootstrap>
    </BrowserRouter>
  );
}
