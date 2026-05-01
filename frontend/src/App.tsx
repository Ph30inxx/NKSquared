import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AppBootstrap from "./components/AppBootstrap";
import AppLayout from "./components/layout/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import ForexRatesPage from "./pages/admin/ForexRatesPage";
import CompanyDetailPage from "./pages/portfolio/CompanyDetailPage";
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
              <Route path="/admin/forex-rates" element={<ForexRatesPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppBootstrap>
    </BrowserRouter>
  );
}
