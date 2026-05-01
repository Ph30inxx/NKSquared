import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";

// ─── Types ────────────────────────────────────────────────────────────────────

export const TRANSACTION_TYPES = [
  "Investment",
  "Follow_on",
  "Partial_exit",
  "Full_exit",
  "Distribution",
  "Write_down",
  "Write_off",
] as const;
export type TransactionType = (typeof TRANSACTION_TYPES)[number];

export const INVESTMENT_STATUSES = [
  "Active",
  "Written_off",
  "Exit_via_IPO",
  "Exit_via_Share_swap",
  "Matured",
] as const;
export type InvestmentStatus = (typeof INVESTMENT_STATUSES)[number];

export const PORTFOLIO_STATUSES = ["Unrealized", "Realized"] as const;
export type PortfolioStatus = (typeof PORTFOLIO_STATUSES)[number];

export const ASSET_CLASSES = [
  "Direct_Equity",
  "Fund_Investment",
  "Debt_Instrument",
] as const;
export type AssetClass = (typeof ASSET_CLASSES)[number];

export const PORTFOLIO_TYPES = [
  "Entity_D_Core",
  "Entity_D_Non_Core",
  "Entity_D_LLC",
  "Entity_E",
  "Entity_A",
  "Strategic_Equity",
  "Entity_C",
  "Real_Estate_Debt",
] as const;
export type PortfolioType = (typeof PORTFOLIO_TYPES)[number];

export interface CompanyListItem {
  id: number;
  company_name: string;
  display_name: string | null;
  portfolio_type: string | null;
  investment_status: string | null;
  portfolio_status: string | null;
  sector: string | null;
  investment_value_cr: string | null;
  current_value_cr: string | null;
  moic: string | null;
  is_active: boolean;
}

export interface CompanyDetail extends CompanyListItem {
  asset_class: string | null;
  sub_sector: string | null;
  country: string | null;
  date_of_first_investment: string | null;
  irr: string | null;
  currency: string;
  reporting_frequency: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedCompanies {
  total: number;
  limit: number;
  offset: number;
  items: CompanyListItem[];
}

export interface CompanyWritePayload {
  company_name: string;
  display_name?: string | null;
  portfolio_type?: string | null;
  investment_status?: InvestmentStatus | null;
  portfolio_status?: PortfolioStatus | null;
  asset_class?: AssetClass | null;
  sector?: string | null;
  sub_sector?: string | null;
  country?: string | null;
  date_of_first_investment?: string | null;
  current_value_cr?: string | number | null;
  currency?: string;
  reporting_frequency?: string;
  notes?: string | null;
}

export interface Transaction {
  id: number;
  company_id: number;
  transaction_date: string;
  transaction_type: string;
  amount_cr: string;
  original_currency: string;
  original_amount: string | null;
  amount_inr_cr: string | null;
  fx_rate_used: string | null;
  series: string | null;
  instrument_type: string | null;
  investing_entity: string | null;
  shares: string | null;
  share_price: string | null;
  pre_money_valuation_cr: string | null;
  post_money_valuation_cr: string | null;
  shareholding_pct: string | null;
  ssa_reference: string | null;
  ssa_recorded_amount: string | null;
  notes: string | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface TransactionWritePayload {
  transaction_date: string;
  transaction_type: TransactionType;
  amount: string | number;
  currency?: string;
  fx_rate_used?: string | number | null;
  series?: string | null;
  instrument_type?: string | null;
  investing_entity?: string | null;
  shares?: string | number | null;
  share_price?: string | number | null;
  pre_money_valuation_cr?: string | number | null;
  post_money_valuation_cr?: string | number | null;
  shareholding_pct?: string | number | null;
  ssa_reference?: string | null;
  ssa_recorded_amount?: string | number | null;
  notes?: string | null;
}

export interface CompanyListParams {
  limit?: number;
  offset?: number;
  sector?: string;
  investment_status?: string;
  portfolio_type?: string;
  q?: string;
  include_inactive?: boolean;
}

// ─── Raw API ──────────────────────────────────────────────────────────────────

export async function listCompanies(params: CompanyListParams = {}): Promise<PaginatedCompanies> {
  const { data } = await api.get<PaginatedCompanies>("/companies", { params });
  return data;
}

export async function getCompany(id: number): Promise<CompanyDetail> {
  const { data } = await api.get<CompanyDetail>(`/companies/${id}`);
  return data;
}

export async function createCompany(payload: CompanyWritePayload): Promise<CompanyDetail> {
  const { data } = await api.post<CompanyDetail>("/companies", payload);
  return data;
}

export async function updateCompany(
  id: number,
  payload: Partial<CompanyWritePayload>,
): Promise<CompanyDetail> {
  const { data } = await api.patch<CompanyDetail>(`/companies/${id}`, payload);
  return data;
}

export async function softDeleteCompany(id: number): Promise<void> {
  await api.delete(`/companies/${id}`);
}

export async function listCompanyTransactions(companyId: number): Promise<Transaction[]> {
  const { data } = await api.get<Transaction[]>(`/companies/${companyId}/transactions`);
  return data;
}

export async function createTransaction(
  companyId: number,
  payload: TransactionWritePayload,
): Promise<Transaction> {
  const { data } = await api.post<Transaction>(`/companies/${companyId}/transactions`, payload);
  return data;
}

export async function updateTransaction(
  id: number,
  payload: Partial<TransactionWritePayload>,
): Promise<Transaction> {
  const { data } = await api.patch<Transaction>(`/transactions/${id}`, payload);
  return data;
}

export async function deleteTransaction(id: number): Promise<void> {
  await api.delete(`/transactions/${id}`);
}

// ─── React Query hooks ────────────────────────────────────────────────────────

const KEYS = {
  list: (params: CompanyListParams) => ["companies", "list", params] as const,
  detail: (id: number) => ["companies", "detail", id] as const,
  transactions: (companyId: number) => ["companies", companyId, "transactions"] as const,
};

export function useCompanies(params: CompanyListParams = {}) {
  return useQuery({
    queryKey: KEYS.list(params),
    queryFn: () => listCompanies(params),
    placeholderData: (prev) => prev,
  });
}

export function useCompany(id: number | null) {
  return useQuery({
    queryKey: id == null ? ["companies", "detail", "none"] : KEYS.detail(id),
    queryFn: () => getCompany(id as number),
    enabled: id != null,
  });
}

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createCompany,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}

export function useUpdateCompany(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<CompanyWritePayload>) => updateCompany(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
  });
}

export function useSoftDeleteCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: softDeleteCompany,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}

export function useCompanyTransactions(companyId: number | null) {
  return useQuery({
    queryKey:
      companyId == null
        ? ["companies", "none", "transactions"]
        : KEYS.transactions(companyId),
    queryFn: () => listCompanyTransactions(companyId as number),
    enabled: companyId != null,
  });
}

export function useCreateTransaction(companyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: TransactionWritePayload) => createTransaction(companyId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.transactions(companyId) });
      qc.invalidateQueries({ queryKey: KEYS.detail(companyId) });
      qc.invalidateQueries({ queryKey: ["companies", "list"] });
    },
  });
}

export function useUpdateTransaction(companyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<TransactionWritePayload> }) =>
      updateTransaction(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.transactions(companyId) });
      qc.invalidateQueries({ queryKey: KEYS.detail(companyId) });
      qc.invalidateQueries({ queryKey: ["companies", "list"] });
    },
  });
}

export function useDeleteTransaction(companyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.transactions(companyId) });
      qc.invalidateQueries({ queryKey: KEYS.detail(companyId) });
      qc.invalidateQueries({ queryKey: ["companies", "list"] });
    },
  });
}
