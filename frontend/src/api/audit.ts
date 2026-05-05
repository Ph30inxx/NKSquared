import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

export interface AuditLogEntry {
  id: number;
  user_id: number | null;
  user_email: string | null;
  entity_type: string;
  entity_id: number;
  action: string;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  ip_address: string | null;
  occurred_at: string;
}

export interface PaginatedAuditLog {
  total: number;
  limit: number;
  offset: number;
  items: AuditLogEntry[];
}

export interface AuditLogParams {
  entity_type?: string;
  entity_id?: number;
  user_id?: number;
  action?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

export async function listAudit(params: AuditLogParams = {}): Promise<PaginatedAuditLog> {
  const { data } = await api.get<PaginatedAuditLog>("/audit/log", { params });
  return data;
}

export function useAuditLog(params: AuditLogParams) {
  return useQuery({
    queryKey: ["audit", "list", params],
    queryFn: () => listAudit(params),
    placeholderData: (prev) => prev,
  });
}

export const ENTITY_TYPES = [
  "portfolio_company",
  "portfolio_transaction",
  "valuation",
  "mis_submission",
] as const;

export const ACTIONS = [
  "CREATE",
  "UPDATE",
  "DELETE",
  "APPROVE",
  "REJECT",
  "UPLOAD",
  "MARK_CURRENT",
] as const;
