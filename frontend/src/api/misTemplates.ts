import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";

export interface MisRowMapping {
  label_regex: string;
  metric_code: string;
  geography?: string | null;
  bu_id?: string | null;
  label_col_index?: number;
}

export interface MisTemplate {
  id: number;
  company_id: string | null;
  name: string;
  version: number;
  is_default: boolean;
  sheet_name_pattern: string | null;
  header_row: number;
  period_orientation: string;
  row_mappings: MisRowMapping[];
  created_by: number | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface MisTemplateCreatePayload {
  company_id?: string | null;
  name: string;
  is_default?: boolean;
  sheet_name_pattern?: string | null;
  header_row?: number;
  period_orientation?: "columns" | "rows";
  row_mappings: MisRowMapping[];
}

export type MisTemplateUpdatePayload = Partial<MisTemplateCreatePayload>;

export interface TemplateCandidateRow {
  row_index: number;
  label: string;
  sample_values: (string | null)[];
}

export interface TemplateCandidatesResponse {
  sheet_names: string[];
  selected_sheet: string;
  header_row: number;
  period_columns: { col_index: number; month_date: string }[];
  rows: TemplateCandidateRow[];
}

export interface TemplateDryRunRow {
  month_date: string;
  geography: string;
  revenue_lacs: string | null;
  cogs_lacs: string | null;
  gross_margin_lacs: string | null;
  ebitda_lacs: string | null;
}

export interface TemplateDryRunResponse {
  monthly_count: number;
  bu_count: number;
  sample_monthly: TemplateDryRunRow[];
  period_year: number;
  period_month: number;
}

export const METRIC_CODES = [
  "revenue_lacs",
  "indirect_income_lacs",
  "total_income_lacs",
  "cogs_lacs",
  "gross_margin_lacs",
  "gross_margin_pct",
  "total_operating_costs_lacs",
  "manpower_cost_lacs",
  "rent_lacs",
  "utilities_lacs",
  "electricity_lacs",
  "channel_expenses_lacs",
  "commission_lacs",
  "transport_lacs",
  "marketing_lacs",
  "admin_lacs",
  "it_lacs",
  "professional_fees_lacs",
  "compliance_costs_lacs",
  "events_lacs",
  "ebitda_lacs",
  "ebitda_pct",
  "itc_reversal_lacs",
  "ebitda_with_itc_lacs",
] as const;

export type MetricCode = (typeof METRIC_CODES)[number];

export async function listTemplates(companyId?: string): Promise<MisTemplate[]> {
  const params = companyId ? { company_id: companyId } : {};
  const { data } = await api.get<MisTemplate[]>("/mis/templates", { params });
  return data;
}

export async function getTemplate(id: number): Promise<MisTemplate> {
  const { data } = await api.get<MisTemplate>(`/mis/templates/${id}`);
  return data;
}

export async function createTemplate(
  payload: MisTemplateCreatePayload,
): Promise<MisTemplate> {
  const { data } = await api.post<MisTemplate>("/mis/templates", payload);
  return data;
}

export async function updateTemplate(
  id: number,
  payload: MisTemplateUpdatePayload,
): Promise<MisTemplate> {
  const { data } = await api.patch<MisTemplate>(`/mis/templates/${id}`, payload);
  return data;
}

export async function setTemplateDefault(id: number): Promise<MisTemplate> {
  const { data } = await api.post<MisTemplate>(`/mis/templates/${id}/set-default`);
  return data;
}

export async function deleteTemplate(id: number): Promise<void> {
  await api.delete(`/mis/templates/${id}`);
}

export async function extractCandidates(
  file: File,
  options: { sheet_name?: string; header_row?: number; label_col_index?: number } = {},
): Promise<TemplateCandidatesResponse> {
  const form = new FormData();
  form.append("file", file);
  if (options.sheet_name) form.append("sheet_name", options.sheet_name);
  form.append("header_row", String(options.header_row ?? 1));
  form.append("label_col_index", String(options.label_col_index ?? 1));
  const { data } = await api.post<TemplateCandidatesResponse>(
    "/mis/templates/extract-candidates",
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function dryRunTemplate(
  templateId: number,
  file: File,
  companyId?: string,
): Promise<TemplateDryRunResponse> {
  const form = new FormData();
  form.append("file", file);
  if (companyId) form.append("company_id", companyId);
  const { data } = await api.post<TemplateDryRunResponse>(
    `/mis/templates/${templateId}/dry-run`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

const KEYS = {
  list: (companyId?: string) => ["mis-templates", "list", companyId] as const,
  detail: (id: number) => ["mis-templates", "detail", id] as const,
};

export function useTemplates(companyId?: string) {
  return useQuery({
    queryKey: KEYS.list(companyId),
    queryFn: () => listTemplates(companyId),
  });
}

export function useTemplate(id: number | null) {
  return useQuery({
    queryKey: id == null ? ["mis-templates", "detail", "none"] : KEYS.detail(id),
    queryFn: () => getTemplate(id as number),
    enabled: id != null,
  });
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTemplate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mis-templates"] }),
  });
}

export function useUpdateTemplate(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: MisTemplateUpdatePayload) => updateTemplate(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mis-templates"] }),
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteTemplate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mis-templates"] }),
  });
}

export function useSetTemplateDefault() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: setTemplateDefault,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mis-templates"] }),
  });
}
