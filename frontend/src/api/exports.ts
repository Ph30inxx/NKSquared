import { api } from "./client";

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoke after a tick so Safari/older browsers finish the download.
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

function stamp(): string {
  return new Date().toISOString().slice(0, 10).replace(/-/g, "");
}

export async function downloadPortfolioXlsx(): Promise<void> {
  const res = await api.get<Blob>("/exports/portfolio.xlsx", {
    responseType: "blob",
  });
  triggerDownload(res.data, `nksquared_portfolio_${stamp()}.xlsx`);
}

export async function downloadMisXlsx(companyId: string): Promise<void> {
  const res = await api.get<Blob>(`/exports/mis/${encodeURIComponent(companyId)}.xlsx`, {
    responseType: "blob",
  });
  triggerDownload(res.data, `mis_${companyId}_${stamp()}.xlsx`);
}

export async function downloadBulkMisXlsx(companyIds: string[]): Promise<void> {
  const res = await api.post<Blob>(
    "/exports/mis/bulk.xlsx",
    { company_ids: companyIds },
    { responseType: "blob" },
  );
  triggerDownload(res.data, `mis_bulk_${stamp()}.xlsx`);
}
