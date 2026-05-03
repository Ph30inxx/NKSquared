import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";

export type MisSubmissionStatus =
  | "Pending"
  | "Submitted"
  | "Under Review"
  | "Approved"
  | "Rejected"
  | "Resubmission Required";

export const MIS_STATUS_FILTERS: (MisSubmissionStatus | "All")[] = [
  "All",
  "Pending",
  "Submitted",
  "Under Review",
  "Approved",
  "Rejected",
];

export interface MisSubmission {
  id: number;
  company_id: string;
  period_year: number;
  period_month: number;
  fiscal_year: string;
  status: MisSubmissionStatus;
  source_file_name: string | null;
  source_file_url: string | null;
  uploaded_at: string | null;
  uploaded_by: number | null;
  reviewed_at: string | null;
  reviewed_by: number | null;
  rejection_reason: string | null;
  anomaly_count: number;
  notes: string | null;
}

export interface MisSubmissionListItem
  extends Omit<MisSubmission, "source_file_url" | "notes"> {}

export interface PaginatedMisSubmissions {
  total: number;
  limit: number;
  offset: number;
  items: MisSubmissionListItem[];
}

export interface MisSubmissionPreviewRow {
  month_date: string;
  geography: string;
  revenue_lacs: string | null;
  cogs_lacs: string | null;
  gross_margin_lacs: string | null;
  ebitda_lacs: string | null;
}

export interface MisSubmissionPreview {
  template: string;
  monthly_count: number;
  bu_count: number;
  outlet_count: number;
  sample_monthly: MisSubmissionPreviewRow[];
}

export interface MisSubmissionCreatePayload {
  company_id: string;
  period_year: number;
  period_month: number;
  fiscal_year?: string;
  notes?: string | null;
}

export interface MisListParams {
  status?: MisSubmissionStatus;
  company_id?: string;
  limit?: number;
  offset?: number;
}

export async function listMisSubmissions(
  params: MisListParams = {},
): Promise<PaginatedMisSubmissions> {
  const { data } = await api.get<PaginatedMisSubmissions>("/mis/submissions", { params });
  return data;
}

export async function getMisSubmission(id: number): Promise<MisSubmission> {
  const { data } = await api.get<MisSubmission>(`/mis/submissions/${id}`);
  return data;
}

export async function createMisSubmission(
  payload: MisSubmissionCreatePayload,
): Promise<MisSubmission> {
  const { data } = await api.post<MisSubmission>("/mis/submissions", payload);
  return data;
}

export async function uploadMisFile(id: number, file: File): Promise<MisSubmission> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<MisSubmission>(
    `/mis/submissions/${id}/upload`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function previewMisSubmission(id: number): Promise<MisSubmissionPreview> {
  const { data } = await api.get<MisSubmissionPreview>(`/mis/submissions/${id}/preview`);
  return data;
}

export async function approveMisSubmission(id: number): Promise<MisSubmission> {
  const { data } = await api.post<MisSubmission>(`/mis/submissions/${id}/approve`);
  return data;
}

export async function rejectMisSubmission(id: number, reason: string): Promise<MisSubmission> {
  const { data } = await api.post<MisSubmission>(`/mis/submissions/${id}/reject`, {
    reason,
  });
  return data;
}

const KEYS = {
  list: (params: MisListParams) => ["mis", "list", params] as const,
  detail: (id: number) => ["mis", "detail", id] as const,
  preview: (id: number) => ["mis", "preview", id] as const,
};

export function useMisSubmissions(params: MisListParams = {}) {
  return useQuery({
    queryKey: KEYS.list(params),
    queryFn: () => listMisSubmissions(params),
    placeholderData: (prev) => prev,
  });
}

export function useMisSubmission(id: number | null) {
  return useQuery({
    queryKey: id == null ? ["mis", "detail", "none"] : KEYS.detail(id),
    queryFn: () => getMisSubmission(id as number),
    enabled: id != null,
  });
}

export function useCreateMisSubmission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createMisSubmission,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mis"] }),
  });
}

export function useUploadMisFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => uploadMisFile(id, file),
    onSuccess: (sub) => {
      qc.invalidateQueries({ queryKey: KEYS.detail(sub.id) });
      qc.invalidateQueries({ queryKey: ["mis", "list"] });
    },
  });
}

export function usePreviewMisSubmission(id: number | null) {
  return useQuery({
    queryKey: id == null ? ["mis", "preview", "none"] : KEYS.preview(id),
    queryFn: () => previewMisSubmission(id as number),
    enabled: false, // explicit refetch via "Refresh preview" button
    retry: false,
  });
}

export function useApproveMisSubmission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: approveMisSubmission,
    onSuccess: (sub) => {
      qc.invalidateQueries({ queryKey: KEYS.detail(sub.id) });
      qc.invalidateQueries({ queryKey: ["mis", "list"] });
    },
  });
}

export function useRejectMisSubmission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      rejectMisSubmission(id, reason),
    onSuccess: (sub) => {
      qc.invalidateQueries({ queryKey: KEYS.detail(sub.id) });
      qc.invalidateQueries({ queryKey: ["mis", "list"] });
    },
  });
}
