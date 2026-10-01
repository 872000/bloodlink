"""Matplotlib visuals: compatibility heatmap + match-results chart."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .compatibility import GROUPS, compatibility_matrix


def compatibility_heatmap(path: str) -> str:
    """Render the 8x8 donor->recipient compatibility matrix as a heatmap."""
    m = compatibility_matrix()
    data = np.array([[1 if m[d][r] else 0 for r in GROUPS] for d in GROUPS])

    fig, ax = plt.subplots(figsize=(8, 7))
    cmap = plt.cm.colors.ListedColormap(["#f2f2f2", "#c0392b"])
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=1)
    ax.set_xticks(range(len(GROUPS)), GROUPS)
    ax.set_yticks(range(len(GROUPS)), GROUPS)
    ax.set_xlabel("Recipient blood group", fontsize=11)
    ax.set_ylabel("Donor blood group", fontsize=11)
    ax.set_title("BloodLink — Donor → Recipient Compatibility Matrix\n"
                 "(red = compatible transfusion)", fontsize=12, pad=12)
    for i in range(len(GROUPS)):
        for j in range(len(GROUPS)):
            ax.text(j, i, "✓" if data[i, j] else "✗",
                    ha="center", va="center",
                    color="white" if data[i, j] else "#999999",
                    fontsize=12, fontweight="bold")
    # annotate universal donor / recipient
    fig.text(0.5, 0.01, "O− = universal donor   •   AB+ = universal recipient",
             ha="center", va="bottom", fontsize=10, style="italic", color="#333333")
    fig.colorbar(im, ax=ax, ticks=[0, 1]).set_ticklabels(["No", "Yes"])
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def match_chart(queue, path: str) -> str:
    """Bar chart of match scores grouped by request (urgency labeled)."""
    if not queue:
        raise ValueError("empty match queue")
    labels, scores, colors = [], [], []
    urg_colors = {5: "#c0392b", 4: "#e67e22", 3: "#f1c40f", 2: "#2ecc71", 1: "#3498db"}
    for req, donor, score, _dist in queue:
        labels.append(f"{req['hospital'][:16]}\n{req['blood_group']} ← {donor['name'].split()[0]}")
        scores.append(score)
        colors.append(urg_colors.get(req["urgency"], "#999999"))

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.1), 5.5))
    bars = ax.bar(range(len(labels)), scores, color=colors, edgecolor="#333333")
    ax.set_xticks(range(len(labels)), labels, fontsize=8, rotation=20, ha="right")
    ax.set_ylabel("Match score (0–1)", fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.set_title("BloodLink — Ranked donor matches (bars colored by request urgency)",
                 fontsize=12, pad=12)
    for bar, s in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{s:.2f}", ha="center", va="bottom", fontsize=8)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in urg_colors.values()]
    ax.legend(handles, [f"Urgency {u}" for u in urg_colors],
              title="Request urgency", loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
