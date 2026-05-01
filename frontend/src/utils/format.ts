/** Format a Decimal-as-string crore amount with a thousands separator. */
export function formatCr(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return "—";
  return num.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Format MOIC as `1.50x`. */
export function formatMoic(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return "—";
  return `${num.toFixed(2)}x`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
}

/** Format a fractional rate (0.183 → "18.3%"). */
export function formatPct(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return "—";
  return `${(num * 100).toFixed(1)}%`;
}

export function moicColor(value: string | number | null | undefined): string | undefined {
  if (value == null || value === "") return undefined;
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return undefined;
  if (num > 1.1) return "#0F6E56";
  if (num < 0.9) return "#A32D2D";
  return undefined;
}
