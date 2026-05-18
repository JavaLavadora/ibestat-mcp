"""Generate the waste-tourism correlation plot for the worked example."""

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

years = [2016, 2017, 2018, 2019, 2020, 2021]
waste_kg = [753.5, 766.0, 828.8, 757.9, 568.3, 605.0]
tourists_m = [15.32, 16.28, 16.55, 16.48, 3.11, 8.68]

r, p = stats.pearsonr(waste_kg, tourists_m)
print(f"Pearson r = {r:.3f}, p-value = {p:.4f}")

fig, ax1 = plt.subplots(figsize=(10, 5.5))

color_waste = "#2E86AB"
color_tour = "#E8553A"

ax1.bar(
    [y - 0.18 for y in years], waste_kg, width=0.35,
    color=color_waste, label="Waste (kg/capita)", zorder=3,
)
ax1.set_xlabel("Year", fontsize=12)
ax1.set_ylabel("Urban waste collected (kg/capita)", color=color_waste, fontsize=12)
ax1.tick_params(axis="y", labelcolor=color_waste)
ax1.set_ylim(0, 950)

ax2 = ax1.twinx()
ax2.bar(
    [y + 0.18 for y in years], tourists_m, width=0.35,
    color=color_tour, label="Tourists (millions)", zorder=3,
)
ax2.set_ylabel("Tourist arrivals (millions)", color=color_tour, fontsize=12)
ax2.tick_params(axis="y", labelcolor=color_tour)
ax2.set_ylim(0, 20)

ax1.set_xticks(years)
ax1.set_xticklabels(years, fontsize=11)
ax1.grid(axis="y", alpha=0.3, zorder=0)

fig.legend(loc="upper left", bbox_to_anchor=(0.12, 0.95), fontsize=11)

plt.title(
    f"Waste per Capita vs Tourist Arrivals — Illes Balears (Pearson r = {r:.2f})",
    fontsize=13, pad=14,
)

plt.tight_layout()
plt.savefig("examples/waste-tourism-correlation.png", dpi=150, bbox_inches="tight")
print("Plot saved to examples/waste-tourism-correlation.png")
