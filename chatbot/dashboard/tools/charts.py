"""
Dashboard chart tools — 12 chart generation tools.

Every tool:
  - Uses matplotlib to render the chart
  - Renders into io.BytesIO, base64-encodes the PNG
  - Stores the result in _chart_store keyed by dashboard_id + ":" + chart_id
  - Returns {"chart_id": str, "title": str, "base64_png": str}
  - Is wrapped with @_thread_safe_chart for concurrency safety and error fallback
"""
import base64
import functools
import io
import threading
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── In-memory chart store ─────────────────────────────────────────────────────
# Keyed by "{dashboard_id}:{chart_id}" — populated during agent run,
# consumed by compile_dashboard, then purged.
_chart_store: dict[str, str] = {}
_chart_lock = threading.Lock()
_mpl_lock = threading.Lock()


def _store(dashboard_id: str, chart_id: str, b64: str) -> None:
    with _chart_lock:
        _chart_store[f"{dashboard_id}:{chart_id}"] = b64


def get_chart(dashboard_id: str, chart_id: str) -> Optional[str]:
    with _chart_lock:
        return _chart_store.get(f"{dashboard_id}:{chart_id}")


def get_all_charts(dashboard_id: str) -> dict[str, str]:
    with _chart_lock:
        prefix = f"{dashboard_id}:"
        return {k[len(prefix):]: v for k, v in _chart_store.items() if k.startswith(prefix)}


def purge_dashboard(dashboard_id: str) -> None:
    with _chart_lock:
        keys = [k for k in _chart_store if k.startswith(f"{dashboard_id}:")]
        for k in keys:
            del _chart_store[k]


# ── Shared NK style ───────────────────────────────────────────────────────────

NK_COLORS = [
    "#2C3E87", "#27AE60", "#E74C3C", "#F39C12", "#8E44AD",
    "#16A085", "#D35400", "#2980B9", "#1ABC9C", "#C0392B",
]

def _apply_nk_style(ax, title: str, x_label: str = "", y_label: str = ""):
    ax.set_facecolor("#FAFAFA")
    ax.figure.patch.set_facecolor("#FAFAFA")
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.set_title(title, fontsize=13, fontweight="bold", color="#1A1A2E", pad=10)
    if x_label:
        ax.set_xlabel(x_label, fontsize=10, color="#444444")
    if y_label:
        ax.set_ylabel(y_label, fontsize=10, color="#444444")
    ax.tick_params(colors="#444444", labelsize=9)


def _to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _error_chart(title: str, message: str) -> str:
    """Generate a placeholder chart image for error states."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.text(0.5, 0.55, "\u26A0  Data Unavailable", ha="center", va="center",
            fontsize=16, color="#E74C3C", fontweight="bold", transform=ax.transAxes)
    ax.text(0.5, 0.40, message[:120], ha="center", va="center",
            fontsize=10, color="#999999", transform=ax.transAxes, style="italic")
    ax.set_title(title, fontsize=13, fontweight="bold", color="#1A1A2E", pad=10)
    ax.axis("off")
    fig.patch.set_facecolor("#FAFAFA")
    return _to_b64(fig)


def _thread_safe_chart(func):
    """Decorator: wraps chart generation with matplotlib lock and error fallback."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with _mpl_lock:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                cid = kwargs.get("chart_id") or (args[1] if len(args) > 1 else "unknown")
                did = kwargs.get("dashboard_id") or (args[0] if args else "unknown")
                ttl = kwargs.get("title") or (args[2] if len(args) > 2 else "Chart")
                b64 = _error_chart(ttl, str(exc))
                _store(did, cid, b64)
                return {"chart_id": cid, "title": ttl, "base64_png": b64, "error": str(exc)}
    return wrapper


def _draw_reference_lines(ax, reference_lines: List[dict], horizontal: bool = True):
    """Draw benchmark/target reference lines on a chart axis."""
    if not reference_lines:
        return
    for ref in reference_lines:
        val = ref.get("value")
        if val is None:
            continue
        color = ref.get("color", "#FF6B6B")
        style = ref.get("style", "--")
        label = ref.get("label", "")
        if horizontal:
            ax.axhline(val, color=color, linestyle=style, linewidth=1.2,
                       label=label, zorder=5, alpha=0.85)
        else:
            ax.axvline(val, color=color, linestyle=style, linewidth=1.2,
                       label=label, zorder=5, alpha=0.85)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — create_bar_chart
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_bar_chart(
    dashboard_id: str,
    chart_id: str,
    title: str,
    labels: List[str],
    datasets: List[dict],
    x_label: str = "",
    y_label: str = "",
    stacked: bool = False,
    horizontal: bool = False,
    value_labels: bool = True,
    reference_lines: Optional[List[dict]] = None,
) -> dict:
    """
    Generate a bar chart (vertical, horizontal, or stacked).

    Args:
        dashboard_id: Unique dashboard run ID.
        chart_id: Semantic identifier (e.g. 'sector_moic_bar').
        title: Chart title.
        labels: Category labels on the axis.
        datasets: [{label, values: [float], color?}]
        stacked: True for stacked bars.
        horizontal: True for horizontal bars (better for long labels).
        value_labels: Show value on top of each bar.
        reference_lines: [{value, label, color?, style?}] — benchmark/target overlay lines.

    Returns:
        {chart_id, title, base64_png}
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    n = len(labels)
    n_ds = len(datasets)
    width = 0.7 / max(n_ds, 1) if not stacked else 0.6
    x = np.arange(n)

    for i, ds in enumerate(datasets):
        color = ds.get("color") or NK_COLORS[i % len(NK_COLORS)]
        values = ds.get("values", [])
        offset = (i - (n_ds - 1) / 2) * width if not stacked else 0
        bottom = None if not stacked or i == 0 else np.sum(
            [np.array(datasets[j]["values"], dtype=float) for j in range(i)], axis=0
        )

        if horizontal:
            bars = ax.barh(x + (0 if stacked else offset), values,
                           height=width, color=color, label=ds.get("label", ""),
                           left=bottom, zorder=3)
            if value_labels:
                for bar in bars:
                    w = bar.get_width()
                    if w != 0:
                        ax.text(w + max(abs(w) * 0.01, 0.1), bar.get_y() + bar.get_height() / 2,
                                f"{w:.1f}", va="center", ha="left", fontsize=8, color="#333")
        else:
            bars = ax.bar(x + (0 if stacked else offset), values,
                          width=width, color=color, label=ds.get("label", ""),
                          bottom=bottom, zorder=3)
            if value_labels:
                for bar in bars:
                    h = bar.get_height()
                    if h != 0:
                        ax.text(bar.get_x() + bar.get_width() / 2, h + max(abs(h) * 0.01, 0.1),
                                f"{h:.1f}", ha="center", va="bottom", fontsize=8, color="#333")

    if horizontal:
        ax.set_yticks(x)
        ax.set_yticklabels(labels, fontsize=9)
        ax.grid(axis="x", color="#E8E8E8", linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
    else:
        ax.set_xticks(x)
        rot = 45 if n > 5 else 0
        ax.set_xticklabels(labels, rotation=rot, ha="right" if rot else "center", fontsize=9)

    _apply_nk_style(ax, title, x_label, y_label)
    _draw_reference_lines(ax, reference_lines, horizontal=not horizontal)

    if n_ds > 1 or reference_lines:
        ax.legend(fontsize=9, framealpha=0)

    fig.tight_layout(pad=1.5)
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — create_line_chart
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_line_chart(
    dashboard_id: str,
    chart_id: str,
    title: str,
    labels: List[str],
    datasets: List[dict],
    x_label: str = "",
    y_label: str = "",
    annotate_last: bool = True,
    fill: bool = False,
    reference_lines: Optional[List[dict]] = None,
) -> dict:
    """
    Generate a line chart for time-series data.

    Args:
        datasets: [{label, values, color?, linestyle?}]
        annotate_last: Label the last data point value.
        fill: Shade area under each line.
        reference_lines: [{value, label, color?, style?}] — benchmark/target overlay lines.

    Returns:
        {chart_id, title, base64_png}
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(labels))

    for i, ds in enumerate(datasets):
        color = ds.get("color") or NK_COLORS[i % len(NK_COLORS)]
        linestyle = ds.get("linestyle", "-")
        values = ds.get("values", [])
        ax.plot(x, values, color=color, linewidth=2.2, linestyle=linestyle,
                marker="o", markersize=5, label=ds.get("label", ""), zorder=3)
        if fill:
            ax.fill_between(x, values, alpha=0.12, color=color)
        if annotate_last and values:
            ax.annotate(f"{values[-1]:.1f}", xy=(x[-1], values[-1]),
                        xytext=(4, 4), textcoords="offset points",
                        fontsize=9, color=color, fontweight="bold")

    ax.set_xticks(x)
    rot = 45 if len(labels) > 5 else 0
    ax.set_xticklabels(labels, rotation=rot, ha="right" if rot else "center", fontsize=9)
    _apply_nk_style(ax, title, x_label, y_label)
    _draw_reference_lines(ax, reference_lines)
    if len(datasets) > 1 or reference_lines:
        ax.legend(fontsize=9, framealpha=0)

    fig.tight_layout(pad=1.5)
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — create_pie_chart
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_pie_chart(
    dashboard_id: str,
    chart_id: str,
    title: str,
    labels: List[str],
    values: List[float],
    donut: bool = True,
    show_pct: bool = True,
) -> dict:
    """
    Generate a pie / donut chart.

    Args:
        donut: True renders a donut (wedge cutout in centre).
        show_pct: Show percentage labels on slices.

    Returns:
        {chart_id, title, base64_png}
    """
    total = sum(values) or 1
    n = len(values)

    # Extend color palette if more slices than NK_COLORS
    colors = (NK_COLORS * ((n // len(NK_COLORS)) + 1))[:n]

    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor("#FAFAFA")

    wedge_props = {"linewidth": 1.5, "edgecolor": "white"}

    wedges, _ = ax.pie(
        values,
        colors=colors,
        startangle=90,
        wedgeprops=wedge_props,
        counterclock=False,
    )

    if donut:
        centre = plt.Circle((0, 0), 0.55, fc="#FAFAFA")
        ax.add_patch(centre)

    # Show percentage inside wedge only when slice is large enough to fit
    if show_pct:
        pct_threshold = 4.0  # % — smaller slices get no in-wedge label
        for wedge, val in zip(wedges, values):
            pct = val / total * 100
            if pct >= pct_threshold:
                angle = (wedge.theta1 + wedge.theta2) / 2
                r = 0.72 if donut else 0.65
                x = r * np.cos(np.radians(angle))
                y = r * np.sin(np.radians(angle))
                ax.text(x, y, f"{pct:.1f}%", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")

    ax.set_title(title, fontsize=13, fontweight="bold", color="#1A1A2E", pad=12)

    # Legend on the right — shows label + percentage for every slice
    legend_labels = [f"{lbl}  {v / total * 100:.1f}%" for lbl, v in zip(labels, values)]
    ax.legend(
        wedges, legend_labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=8.5,
        frameon=False,
        handlelength=1.2,
        handleheight=1.2,
    )

    fig.tight_layout()
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — create_kpi_cards
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_kpi_cards(
    dashboard_id: str,
    chart_id: str,
    metrics: List[dict],
) -> dict:
    """
    Generate a row of KPI summary cards.

    Args:
        metrics: [{label, value, unit?, delta?, delta_label?, color?, rag?}]
                 e.g. {label:"Total AUM", value:420, unit:"Cr", delta:+5.2, delta_label:"vs last quarter"}
                 rag: optional "red" | "amber" | "green" — draws a coloured RAG border on the card.

    Returns:
        {chart_id, title, base64_png}
    """
    import textwrap

    n = len(metrics)
    # Cap cards per row at 5; if more, wrap onto two rows
    cols = min(n, 5)
    rows_count = (n + cols - 1) // cols
    card_w = 2.8
    card_h = 1.8 if rows_count == 1 else 1.6
    fig_w = cols * card_w
    fig_h = rows_count * card_h + 0.1

    fig, axes = plt.subplots(rows_count, cols,
                             figsize=(fig_w, fig_h),
                             squeeze=False)
    fig.patch.set_facecolor("#FAFAFA")

    # Flatten and hide any unused axes (when n < rows*cols)
    all_axes = [ax for row in axes for ax in row]
    for ax in all_axes[n:]:
        ax.axis("off")

    for ax, m in zip(all_axes[:n], metrics):
        ax.set_facecolor("white")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("#E0E0E0")
            spine.set_linewidth(0.8)

        # RAG (Red/Amber/Green) border — overrides default border colour
        _RAG_COLORS = {"red": "#E74C3C", "amber": "#F39C12", "green": "#27AE60"}
        rag = m.get("rag")
        if rag and rag.lower() in _RAG_COLORS:
            for spine in ax.spines.values():
                spine.set_color(_RAG_COLORS[rag.lower()])
                spine.set_linewidth(2.5)

        color = m.get("color", NK_COLORS[0])
        val = m.get("value")
        unit = m.get("unit", "")
        val_str = f"{val:,.1f}" if isinstance(val, float) else str(val)
        display = f"{val_str} {unit}".strip()

        # Wrap long labels so they never overflow the card width
        label_raw = m.get("label", "")
        label_wrapped = "\n".join(textwrap.wrap(label_raw, width=18))
        label_lines = label_wrapped.count("\n") + 1
        label_fontsize = 7.5 if label_lines > 1 else 8.5
        label_y = 0.78 if label_lines == 1 else 0.82

        ax.text(0.5, label_y, label_wrapped, ha="center", va="center",
                fontsize=label_fontsize, color="#666666", transform=ax.transAxes,
                multialignment="center", linespacing=1.3)

        value_fontsize = 13 if len(display) > 10 else 15
        ax.text(0.5, 0.44, display, ha="center", va="center",
                fontsize=value_fontsize, color=color, fontweight="bold",
                transform=ax.transAxes)

        if m.get("delta") is not None:
            delta = m["delta"]
            delta_color = "#27AE60" if delta >= 0 else "#E74C3C"
            arrow = "▲" if delta >= 0 else "▼"
            delta_lbl = m.get("delta_label", "")
            delta_text = f"{arrow} {abs(delta):.1f}%"
            if delta_lbl:
                delta_text += f"\n{delta_lbl}"
            ax.text(0.5, 0.15, delta_text, ha="center", va="center",
                    fontsize=7, color=delta_color, transform=ax.transAxes,
                    multialignment="center")

    fig.tight_layout(pad=0.4, h_pad=0.3, w_pad=0.3)
    title = "Key Performance Indicators"
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 5 — create_table_image
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_table_image(
    dashboard_id: str,
    chart_id: str,
    title: str,
    headers: List[str],
    rows: List[List],
    highlight_last_row: bool = False,
    col_widths: Optional[List[float]] = None,
) -> dict:
    """
    Render tabular data as a PNG image.

    Args:
        headers: Column header strings.
        rows: List of row lists (values will be str-converted).
        highlight_last_row: Bold/grey the last row (for totals).
        col_widths: Relative column widths (defaults to equal).

    Returns:
        {chart_id, title, base64_png}
    """
    n_cols = len(headers)
    n_rows = len(rows)
    row_h = 0.5
    fig_h = max(2.0, 0.6 + (n_rows + 1) * row_h + 0.4)
    fig_w = max(9, n_cols * 2.2)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    fig.patch.set_facecolor("#FAFAFA")

    all_data = [headers] + [[str(c) for c in r] for r in rows]
    cell_colors = []
    for i in range(len(all_data)):
        if i == 0:
            cell_colors.append(["#2C3E87"] * n_cols)
        elif highlight_last_row and i == len(all_data) - 1:
            cell_colors.append(["#F0F0F0"] * n_cols)
        else:
            cell_colors.append(["#FFFFFF" if i % 2 == 1 else "#FAFAFA"] * n_cols)

    col_w = col_widths or [1.0 / n_cols] * n_cols

    table = ax.table(
        cellText=all_data,
        cellColours=cell_colors,
        colWidths=col_w,
        loc="upper center",
        cellLoc="center",
        bbox=[0, 0, 1, 1],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    # Scale row height so the table fills the figure properly
    scale_y = fig_h / ((n_rows + 1) * 0.25)
    table.scale(1, scale_y)

    for (row_idx, col_idx), cell in table.get_celld().items():
        cell.set_linewidth(0.4)
        cell.set_edgecolor("#E0E0E0")
        if row_idx == 0:
            cell.set_text_props(color="white", fontweight="bold")
        elif highlight_last_row and row_idx == len(all_data) - 1:
            cell.set_text_props(fontweight="bold")

    ax.set_title(title, fontsize=12, fontweight="bold", color="#1A1A2E", pad=10)
    fig.tight_layout(pad=0.5)
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 6 — create_waterfall_chart  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_waterfall_chart(
    dashboard_id: str,
    chart_id: str,
    title: str,
    labels: List[str],
    values: List[float],
    total_indices: List[int],
    y_label: str = "",
    color_positive: str = "#27AE60",
    color_negative: str = "#E74C3C",
    color_total: str = "#2C3E87",
) -> dict:
    """
    Generate a waterfall (bridge) chart.

    Args:
        labels: Bar labels.
        values: positive = increase, negative = decrease.
        total_indices: Indices rendered as full-height totals (e.g. first and last bars).

    Returns:
        {chart_id, title, base64_png}
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    n = len(labels)
    running = 0.0
    bottoms = []
    colors = []
    display_values = []

    for i, v in enumerate(values):
        if i in total_indices:
            # Negative totals (e.g. negative EBITDA) go below zero
            if v >= 0:
                bottoms.append(0)
                display_values.append(v)
            else:
                bottoms.append(v)          # bar bottom at the negative value
                display_values.append(-v)  # bar height = abs(v), drawn upward to 0
            colors.append(color_total)
            running = v
        else:
            bottoms.append(running if v >= 0 else running + v)
            colors.append(color_positive if v >= 0 else color_negative)
            display_values.append(abs(v))
            running += v

    x = np.arange(n)
    bars = ax.bar(x, display_values, bottom=bottoms, color=colors, width=0.6, zorder=3,
                  edgecolor="white", linewidth=0.8)

    # Connector lines
    prev_top = None
    for i, (bot, h, v) in enumerate(zip(bottoms, display_values, values)):
        # "top" of bar from data perspective: for negative totals top = 0
        top = bot + h
        if prev_top is not None and i not in total_indices:
            ax.plot([i - 0.7, i - 0.3], [prev_top, prev_top],
                    color="#AAAAAA", linewidth=0.8, linestyle="--", zorder=2)
        prev_top = v if i in total_indices else top

    # Value labels — always show the actual signed value
    total_set = set(total_indices)
    for bar, v, i in zip(bars, values, range(n)):
        h = bar.get_height()
        b = bar.get_y()
        label_y = b + h + max(abs(h) * 0.01, 0.2) if v >= 0 else b - max(abs(h) * 0.01, 0.2)
        va = "bottom" if v >= 0 else "top"
        label = f"{v:.1f}" if i in total_set else f"{v:+.1f}"
        ax.text(bar.get_x() + bar.get_width() / 2, label_y, label,
                ha="center", va=va, fontsize=8.5, color="#333")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20 if n > 6 else 0, ha="right" if n > 6 else "center", fontsize=9)
    _apply_nk_style(ax, title, "", y_label)

    legend_patches = [
        mpatches.Patch(color=color_positive, label="Increase"),
        mpatches.Patch(color=color_negative, label="Decrease"),
        mpatches.Patch(color=color_total, label="Total"),
    ]
    ax.legend(handles=legend_patches, fontsize=9, framealpha=0, loc="upper right")
    fig.tight_layout()
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 7 — create_combo_chart  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_combo_chart(
    dashboard_id: str,
    chart_id: str,
    title: str,
    labels: List[str],
    bar_datasets: List[dict],
    line_datasets: List[dict],
    bar_y_label: str = "₹ Lacs",
    line_y_label: str = "%",
    bar_stacked: bool = False,
    reference_lines: Optional[List[dict]] = None,
) -> dict:
    """
    Generate a combo chart: bars on left Y-axis + lines on right Y-axis.

    The primary use case is Revenue (bars) + EBITDA margin % (line).

    Args:
        bar_datasets: [{label, values, color?}] — left Y-axis
        line_datasets: [{label, values, color?}] — right Y-axis (%)
        reference_lines: [{value, label, color?, style?}] — benchmark/target overlay lines (drawn on left Y-axis).

    Returns:
        {chart_id, title, base64_png}
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    ax2 = ax.twinx()
    n = len(labels)
    x = np.arange(n)
    n_bar = len(bar_datasets)
    width = 0.6 / max(n_bar, 1) if not bar_stacked else 0.6

    # Bars
    for i, ds in enumerate(bar_datasets):
        color = ds.get("color") or NK_COLORS[i % len(NK_COLORS)]
        offset = (i - (n_bar - 1) / 2) * width if not bar_stacked else 0
        bottom = None if not bar_stacked or i == 0 else np.sum(
            [np.array(bar_datasets[j]["values"], dtype=float) for j in range(i)], axis=0
        )
        ax.bar(x + offset, ds["values"], width=width, color=color,
               label=ds.get("label", ""), alpha=0.85, bottom=bottom, zorder=3)

    # Lines on right axis
    line_colors = NK_COLORS[n_bar:]
    for i, ds in enumerate(line_datasets):
        color = ds.get("color") or line_colors[i % len(line_colors)]
        ax2.plot(x, ds["values"], color=color, linewidth=2.2,
                 marker="o", markersize=5, label=ds.get("label", ""), zorder=4)
        if ds["values"]:
            ax2.annotate(f"{ds['values'][-1]:.1f}%", xy=(x[-1], ds["values"][-1]),
                         xytext=(4, 4), textcoords="offset points",
                         fontsize=9, color=color, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30 if n > 6 else 0,
                       ha="right" if n > 6 else "center", fontsize=9)
    _apply_nk_style(ax, title, "", bar_y_label)
    _draw_reference_lines(ax, reference_lines)

    ax2.set_ylabel(line_y_label, fontsize=10, color="#444444")
    ax2.tick_params(colors="#444444", labelsize=9)
    ax2.spines["top"].set_visible(False)
    ax2.spines["left"].set_visible(False)

    # Combined legend
    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    if handles1 or handles2 or reference_lines:
        ax.legend(handles1 + handles2, labels1 + labels2, fontsize=9, framealpha=0, loc="upper left")

    fig.tight_layout()
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 8 — create_scatter_chart  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_scatter_chart(
    dashboard_id: str,
    chart_id: str,
    title: str,
    points: List[dict],
    x_label: str = "",
    y_label: str = "",
    annotate_points: bool = True,
    quadrant_lines: dict = None,
) -> dict:
    """
    Generate a scatter chart for portfolio positioning maps.

    Args:
        points: [{label, x, y, size?, color?}]
        quadrant_lines: {x: float, y: float} — draws dividing quadrant lines.

    Returns:
        {chart_id, title, base64_png}
    """
    fig, ax = plt.subplots(figsize=(12, 7))

    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    cx = np.mean(xs) if xs else 0
    cy = np.mean(ys) if ys else 0

    annotations = []
    for i, p in enumerate(points):
        color = p.get("color") or NK_COLORS[i % len(NK_COLORS)]
        size = p.get("size") or 100
        ax.scatter(p["x"], p["y"], s=size, color=color, alpha=0.85, zorder=3,
                   edgecolors="white", linewidths=1.0)
        if annotate_points:
            # Offset label away from cluster centre so labels radiate outward
            dx = p["x"] - cx
            dy = p["y"] - cy
            mag = max((dx**2 + dy**2) ** 0.5, 1e-6)
            ox = (dx / mag) * 14 + 4
            oy = (dy / mag) * 14 + 4
            ann = ax.annotate(
                p.get("label", ""),
                xy=(p["x"], p["y"]),
                xytext=(ox, oy),
                textcoords="offset points",
                fontsize=8,
                color="#333333",
                arrowprops=dict(arrowstyle="-", color="#CCCCCC", lw=0.6),
                zorder=4,
            )
            annotations.append(ann)

    if quadrant_lines:
        qx = quadrant_lines.get("x")
        qy = quadrant_lines.get("y")
        if qx is not None:
            ax.axvline(qx, color="#AAAAAA", linewidth=1, linestyle="--", zorder=1)
        if qy is not None:
            ax.axhline(qy, color="#AAAAAA", linewidth=1, linestyle="--", zorder=1)

    _apply_nk_style(ax, title, x_label, y_label)
    fig.tight_layout(pad=1.5)
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 9 — create_stacked_area_chart  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_stacked_area_chart(
    dashboard_id: str,
    chart_id: str,
    title: str,
    labels: List[str],
    datasets: List[dict],
    x_label: str = "",
    y_label: str = "",
    normalized: bool = False,
    alpha: float = 0.75,
) -> dict:
    """
    Generate a stacked area chart.

    Args:
        datasets: [{label, values, color?}] — stacked layers bottom-up.
        normalized: True → stack to 100% (proportion over time).

    Returns:
        {chart_id, title, base64_png}
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(labels))

    data_arrays = [np.array(ds["values"], dtype=float) for ds in datasets]

    if normalized:
        totals = np.sum(data_arrays, axis=0)
        totals = np.where(totals == 0, 1, totals)
        data_arrays = [d / totals * 100 for d in data_arrays]

    colors = [ds.get("color") or NK_COLORS[i % len(NK_COLORS)] for i, ds in enumerate(datasets)]
    labels_ds = [ds.get("label", f"Series {i+1}") for i, ds in enumerate(datasets)]

    ax.stackplot(x, *data_arrays, labels=labels_ds, colors=colors, alpha=alpha)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30 if len(labels) > 6 else 0,
                       ha="right" if len(labels) > 6 else "center", fontsize=9)
    _apply_nk_style(ax, title, x_label, "% Share" if normalized else y_label)

    if normalized:
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))

    ax.legend(loc="upper left", fontsize=9, framealpha=0)
    fig.tight_layout()
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 10 — create_bullet_chart  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_bullet_chart(
    dashboard_id: str,
    chart_id: str,
    title: str,
    metrics: List[dict],
) -> dict:
    """
    Generate a bullet chart for actual vs target comparisons.

    Args:
        metrics: [{label: str, actual: float, target: float, ranges: List[float]}]
                 ranges should be 3 values like [poor_max, ok_max, good_max]

    Returns:
        {chart_id, title, base64_png}
    """
    fig, ax = plt.subplots(figsize=(10, len(metrics) * 1.0 + 1))
    
    # Configuration
    h = 0.5
    y_pos = np.arange(len(metrics))
    
    for i, m in enumerate(metrics):
        ranges = m.get('ranges', [])
        if len(ranges) == 3:
            ax.barh(y_pos[i], ranges[2], color='#EEEEEE', height=h)
            ax.barh(y_pos[i], ranges[1], color='#DDDDDD', height=h)
            ax.barh(y_pos[i], ranges[0], color='#CCCCCC', height=h)
            
        ax.barh(y_pos[i], m.get('actual', 0), color='#2C3E87', height=h/2)
        ax.plot([m.get('target', 0), m.get('target', 0)], [y_pos[i]-h/1.5, y_pos[i]+h/1.5], color='#E74C3C', linewidth=3)
        
    ax.set_yticks(y_pos)
    ax.set_yticklabels([m.get('label', '') for m in metrics])
    _apply_nk_style(ax, title, '', '')
    
    # Legend for ranges, actual, target
    custom_lines = [
        mpatches.Patch(color='#CCCCCC', label='Poor'),
        mpatches.Patch(color='#DDDDDD', label='Ok'),
        mpatches.Patch(color='#EEEEEE', label='Good'),
        mpatches.Patch(color='#2C3E87', label='Actual'),
        matplotlib.lines.Line2D([0], [0], color='#E74C3C', lw=3, label='Target')
    ]
    ax.legend(handles=custom_lines, loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=5, framealpha=0)
    
    fig.tight_layout()
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 11 — create_heatmap  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_heatmap(
    dashboard_id: str,
    chart_id: str,
    title: str,
    row_labels: List[str],
    col_labels: List[str],
    values: List[List[float]],
    color_scale: str = "RdYlGn",
    annotate: bool = True,
) -> dict:
    """
    Generate a heatmap.
    
    Args:
        values: 2D array of floats
        
    Returns:
        {chart_id, title, base64_png}
    """
    fig, ax = plt.subplots(figsize=(max(8, len(col_labels) * 1.0), max(5, len(row_labels) * 0.5)))
    
    data = np.array(values)
    im = ax.imshow(data, cmap=color_scale, aspect='auto')
    
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_xticklabels(col_labels)
    ax.set_yticklabels(row_labels)
    
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    
    if annotate:
        for i in range(len(row_labels)):
            for j in range(len(col_labels)):
                val = data[i, j]
                # Choose text color based on background (heuristic for RdYlGn)
                text_color = "white" if abs(val) > np.max(np.abs(data)) * 0.6 else "black"
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", color=text_color, fontsize=8)
                
    _apply_nk_style(ax, title)
    # Restore grid for heatmap off
    ax.grid(False)
    
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 12 — create_treemap  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

@_thread_safe_chart
def create_treemap(
    dashboard_id: str,
    chart_id: str,
    title: str,
    labels: List[str],
    sizes: List[float],
) -> dict:
    """
    Generate a treemap.
    
    Args:
        labels: List of category labels
        sizes: Corresponding sizes/values
        
    Returns:
        {chart_id, title, base64_png}
    """
    try:
        import squarify
    except ImportError:
        return {"chart_id": chart_id, "title": title, "base64_png": _error_chart(title, "squarify library not installed. Cannot render treemap.")}
        
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = (NK_COLORS * ((len(sizes) // len(NK_COLORS)) + 1))[:len(sizes)]
    
    # Calculate percentages for labels
    total = sum(sizes) or 1
    pcts = [s / total * 100 for s in sizes]
    display_labels = [f"{l}\n{s:,.1f}\n({p:.1f}%)" for l, s, p in zip(labels, sizes, pcts)]
    
    squarify.plot(sizes=sizes, label=display_labels, color=colors, alpha=0.8, ax=ax,
                  text_kwargs={'fontsize': 9, 'color': 'white', 'fontweight': 'bold'})
                  
    ax.axis('off')
    ax.set_title(title, fontsize=13, fontweight="bold", color="#1A1A2E", pad=10)
    fig.patch.set_facecolor("#FAFAFA")
    
    fig.tight_layout()
    b64 = _to_b64(fig)
    _store(dashboard_id, chart_id, b64)
    return {"chart_id": chart_id, "title": title, "base64_png": b64}
