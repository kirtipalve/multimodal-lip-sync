"""
Generate Single GPU Comparison Chart for Presentation
Author: Kirti Palve
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Create output directory
output_dir = Path("presentation_charts")
output_dir.mkdir(exist_ok=True)

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
colors = {'T4': '#2ecc71', 'A10G': '#3498db', 'A100': '#e74c3c'}

# Data
video_lengths = ['1 min', '5 min', '10 min']
processing_times = {
    'T4': [58, 290, 580],
    'A10G': [59, 295, 590],
    'A100': [40, 200, 400]
}
cost_per_video = {
    'T4': [0.0097, 0.048, 0.097],
    'A10G': [0.021, 0.105, 0.210],
    'A100': [0.044, 0.222, 0.444]
}

# ============== Combined Performance & Cost Chart ==============
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

x = np.arange(len(video_lengths))
width = 0.25

# Left: Processing Time
bars1 = ax1.bar(x - width, processing_times['T4'], width, label='T4', color=colors['T4'], alpha=0.8)
bars2 = ax1.bar(x, processing_times['A10G'], width, label='A10G', color=colors['A10G'], alpha=0.8)
bars3 = ax1.bar(x + width, processing_times['A100'], width, label='A100', color=colors['A100'], alpha=0.8)

# Add timeout warning line
ax1.axhline(y=600, color='red', linestyle='--', linewidth=2, label='Timeout (600s)', alpha=0.7)

# Add value labels
for bars in [bars1, bars2, bars3]:
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}s',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

ax1.set_xlabel('Video Length', fontsize=12, fontweight='bold')
ax1.set_ylabel('Processing Time (seconds)', fontsize=12, fontweight='bold')
ax1.set_title('Processing Time', fontsize=13, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(video_lengths)
ax1.legend(fontsize=10, loc='upper left')
ax1.grid(axis='y', alpha=0.3)

# Right: Cost per Video
bars1 = ax2.bar(x - width, cost_per_video['T4'], width, label='T4', color=colors['T4'], alpha=0.8)
bars2 = ax2.bar(x, cost_per_video['A10G'], width, label='A10G', color=colors['A10G'], alpha=0.8)
bars3 = ax2.bar(x + width, cost_per_video['A100'], width, label='A100', color=colors['A100'], alpha=0.8)

# Add value labels
for bars in [bars1, bars2, bars3]:
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'${height:.3f}',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

ax2.set_xlabel('Video Length', fontsize=12, fontweight='bold')
ax2.set_ylabel('Cost per Video (USD)', fontsize=12, fontweight='bold')
ax2.set_title('Cost per Video', fontsize=13, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(video_lengths)
ax2.legend(fontsize=10, loc='upper left')
ax2.grid(axis='y', alpha=0.3)

# Overall title
fig.suptitle('GPU Performance Analysis: T4 Selected for Production\n78% Cost Savings vs A100 | Adequate Speed for Batch Workflows',
             fontsize=15, fontweight='bold', y=1.02)

# Add decision box
decision_text = "DECISION: T4 GPU\n\nWhy:\n• 78% cheaper than A100\n• Similar speed to A10G\n• Safe for videos <8 min\n• Best cost/performance ratio"
fig.text(0.5, -0.08, decision_text, ha='center', fontsize=12,
         bbox=dict(boxstyle='round,pad=1', facecolor='lightgreen', alpha=0.8, edgecolor='green', linewidth=2))

plt.tight_layout()
plt.savefig(output_dir / 'gpu_comparison_final.png', dpi=300, bbox_inches='tight')
print(f"✅ Chart saved: {output_dir / 'gpu_comparison_final.png'}")
plt.close()
