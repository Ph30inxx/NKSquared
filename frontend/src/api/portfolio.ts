import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

export interface PortfolioSummary {
  total_invested_cr: string;
  current_value_cr: string;
  weighted_moic: string | null;
  company_count: number;
  pending_mis_count: number;
}

export interface PortfolioBucket {
  key: string;
  invested_cr: string;
  current_cr: string;
  weighted_moic: string | null;
  count: number;
}

export interface DashboardOverview {
  summary: PortfolioSummary;
  by_sector: PortfolioBucket[];
  by_vintage: PortfolioBucket[];
  by_category: PortfolioBucket[];
}

async function getDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await api.get<DashboardOverview>(
    "/dashboards/portfolio-overview",
  );
  return data;
}

async function getBySector(): Promise<PortfolioBucket[]> {
  const { data } = await api.get<PortfolioBucket[]>("/portfolio/by-sector");
  return data;
}

async function getByVintage(): Promise<PortfolioBucket[]> {
  const { data } = await api.get<PortfolioBucket[]>("/portfolio/by-vintage");
  return data;
}

async function getByCategory(): Promise<PortfolioBucket[]> {
  const { data } = await api.get<PortfolioBucket[]>("/portfolio/by-category");
  return data;
}

const KEYS = {
  overview: ["portfolio", "overview"] as const,
  sector: ["portfolio", "by-sector"] as const,
  vintage: ["portfolio", "by-vintage"] as const,
  category: ["portfolio", "by-category"] as const,
};

export function useDashboardOverview() {
  return useQuery({ queryKey: KEYS.overview, queryFn: getDashboardOverview });
}

export function useBySector() {
  return useQuery({ queryKey: KEYS.sector, queryFn: getBySector });
}

export function useByVintage() {
  return useQuery({ queryKey: KEYS.vintage, queryFn: getByVintage });
}

export function useByCategory() {
  return useQuery({ queryKey: KEYS.category, queryFn: getByCategory });
}
