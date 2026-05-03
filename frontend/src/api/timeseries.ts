import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

export interface TimeseriesPoint {
  month: string;
  value: string | null;
  mom_pct: string | null;
}

export type FlatSeries = Record<string, TimeseriesPoint[]>;
export type GeoSeries = Record<string, Record<string, TimeseriesPoint[]>>;

export interface TimeseriesResponse {
  company_code: string;
  months: string[];
  series: FlatSeries | GeoSeries;
}

export interface CompanySummaryResponse {
  company_code: string;
  latest_month: string;
  kpis: Record<
    string,
    { value: string | null; prev_value: string | null; mom_pct: string | null }
  >;
  waterfall: { label: string; value: string | null; kind: string }[];
  bu_breakdown: {
    bu_id: string | null;
    revenue_lacs: string | null;
    gross_margin_lacs: string | null;
    gross_margin_pct: string | null;
    ebitda_lacs: string | null;
    ebitda_pct: string | null;
  }[];
  channel_mix: Record<string, string>;
  latest_submission_id: number | null;
  anomaly_count: number;
}

export interface TimeseriesParams {
  metrics?: string[];
  from?: string;
  to?: string;
  breakdown?: "none" | "geography" | "channels";
}

async function getTimeseries(
  companyCode: string,
  params: TimeseriesParams = {},
): Promise<TimeseriesResponse> {
  const { data } = await api.get<TimeseriesResponse>(
    `/mis/companies/${encodeURIComponent(companyCode)}/timeseries`,
    {
      params: {
        metrics: params.metrics?.join(",") || undefined,
        from: params.from,
        to: params.to,
        breakdown: params.breakdown,
      },
    },
  );
  return data;
}

async function getCompanySummary(
  companyCode: string,
): Promise<CompanySummaryResponse> {
  const { data } = await api.get<CompanySummaryResponse>(
    `/mis/companies/${encodeURIComponent(companyCode)}/summary`,
  );
  return data;
}

const KEYS = {
  ts: (code: string, params: TimeseriesParams) =>
    ["mis", "timeseries", code, params] as const,
  summary: (code: string) => ["mis", "summary", code] as const,
};

export function useCompanyTimeseries(
  companyCode: string | null | undefined,
  params: TimeseriesParams = {},
) {
  return useQuery({
    queryKey: KEYS.ts(companyCode || "", params),
    queryFn: () => getTimeseries(companyCode as string, params),
    enabled: Boolean(companyCode),
  });
}

export function useCompanySummary(companyCode: string | null | undefined) {
  return useQuery({
    queryKey: KEYS.summary(companyCode || ""),
    queryFn: () => getCompanySummary(companyCode as string),
    enabled: Boolean(companyCode),
    retry: (count, err: any) => {
      // 404 means no MIS yet — don't retry.
      if (err?.response?.status === 404) return false;
      return count < 2;
    },
  });
}
