import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";

export interface ForexRate {
  id: number;
  from_currency: string;
  to_currency: string;
  rate: string;
  effective_date: string;
  source: string | null;
  created_at: string;
}

export interface ForexRateCreatePayload {
  from_currency: string;
  to_currency?: string;
  rate: string | number;
  effective_date: string;
  source?: string | null;
}

export interface ForexRateListParams {
  from?: string;
  to?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
}

export async function listForexRates(params: ForexRateListParams = {}): Promise<ForexRate[]> {
  const { data } = await api.get<ForexRate[]>("/forex-rates", { params });
  return data;
}

export async function upsertForexRate(payload: ForexRateCreatePayload): Promise<ForexRate> {
  const { data } = await api.post<ForexRate>("/forex-rates", payload);
  return data;
}

export async function bulkUpsertForexRates(
  rates: ForexRateCreatePayload[],
): Promise<ForexRate[]> {
  const { data } = await api.post<ForexRate[]>("/forex-rates/bulk", { rates });
  return data;
}

export function useForexRates(params: ForexRateListParams = {}) {
  return useQuery({
    queryKey: ["forex-rates", params],
    queryFn: () => listForexRates(params),
    placeholderData: (prev) => prev,
  });
}

export function useUpsertForexRate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: upsertForexRate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["forex-rates"] }),
  });
}
