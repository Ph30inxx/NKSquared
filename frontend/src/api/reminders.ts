import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";

export const REMINDER_TYPES = [
  "MIS_MONTHLY",
  "MIS_QUARTERLY",
  "VALUATION_REVIEW",
  "CUSTOM",
] as const;
export type ReminderType = (typeof REMINDER_TYPES)[number];

export interface ReminderSchedule {
  id: number;
  company_id: number;
  reminder_type: ReminderType;
  enabled: boolean;
  cadence_days: number;
  first_reminder_offset_days: number;
  escalation_threshold: number;
  escalation_contact_id: number | null;
}

export interface ReminderScheduleWritePayload {
  company_id: number;
  reminder_type?: ReminderType;
  enabled?: boolean;
  cadence_days?: number;
  first_reminder_offset_days?: number;
  escalation_threshold?: number;
  escalation_contact_id?: number | null;
}

export interface ReminderLog {
  id: number;
  schedule_id: number | null;
  company_id: number;
  sent_at: string;
  channel: string;
  recipient_email: string | null;
  subject: string | null;
  status: string;
  is_escalation: boolean;
  related_period: string | null;
}

export interface PaginatedReminderLogs {
  total: number;
  limit: number;
  offset: number;
  items: ReminderLog[];
}

interface ListLogsParams {
  company_id?: number;
  limit?: number;
  offset?: number;
}

export async function listSchedules(companyId?: number): Promise<ReminderSchedule[]> {
  const { data } = await api.get<ReminderSchedule[]>("/reminders/schedules", {
    params: companyId != null ? { company_id: companyId } : {},
  });
  return data;
}

export async function createSchedule(
  payload: ReminderScheduleWritePayload,
): Promise<ReminderSchedule> {
  const { data } = await api.post<ReminderSchedule>("/reminders/schedules", payload);
  return data;
}

export async function updateSchedule(
  id: number,
  payload: Partial<ReminderScheduleWritePayload>,
): Promise<ReminderSchedule> {
  const { data } = await api.patch<ReminderSchedule>(`/reminders/schedules/${id}`, payload);
  return data;
}

export async function deleteSchedule(id: number): Promise<void> {
  await api.delete(`/reminders/schedules/${id}`);
}

export async function listReminderLogs(
  params: ListLogsParams = {},
): Promise<PaginatedReminderLogs> {
  const { data } = await api.get<PaginatedReminderLogs>("/reminders/logs", { params });
  return data;
}

export async function sendReminderNow(
  companyId: number,
  isEscalation = false,
): Promise<ReminderLog> {
  const { data } = await api.post<ReminderLog>(
    `/reminders/companies/${companyId}/send-now`,
    { is_escalation: isEscalation },
  );
  return data;
}

const KEYS = {
  schedules: (companyId?: number) => ["reminders", "schedules", companyId ?? "all"] as const,
  logs: (params: ListLogsParams) => ["reminders", "logs", params] as const,
};

export function useReminderSchedules(companyId?: number) {
  return useQuery({
    queryKey: KEYS.schedules(companyId),
    queryFn: () => listSchedules(companyId),
  });
}

export function useCreateReminderSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createSchedule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reminders"] }),
  });
}

export function useUpdateReminderSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<ReminderScheduleWritePayload> }) =>
      updateSchedule(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reminders"] }),
  });
}

export function useDeleteReminderSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reminders"] }),
  });
}

export function useReminderLogs(params: ListLogsParams = {}) {
  return useQuery({
    queryKey: KEYS.logs(params),
    queryFn: () => listReminderLogs(params),
    placeholderData: (prev) => prev,
  });
}

export function useSendReminderNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ companyId, isEscalation }: { companyId: number; isEscalation?: boolean }) =>
      sendReminderNow(companyId, isEscalation ?? false),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reminders", "logs"] }),
  });
}
