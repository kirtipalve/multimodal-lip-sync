"""
Generate GPU Comparison Charts for Presentation
Creates visualizations comparing T4, A10G, and A100 performance and cost metrics.

Author: Kirti Palve
Usage: python generate_charts.py
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

# ============== Chart 1: Processing Time Comparison ==============
fig, ax = plt.subplots(figsize=(12, 6))

x = np.arange(len(video_lengths))
width = 0.25

bars1 = ax.bar(x - width, processing_times['T4'], width, label='T4', color=colors['T4'], alpha=0.8)
bars2 = ax.bar(x, processing_times['A10G'], width, label='A10G', color=colors['A10G'], alpha=0.8)
bars3 = ax.bar(x + width, processing_times['A100'], width, label='A100', color=colors['A100'], alpha=0.8)

# Add timeout warning line
ax.axhline(y=600, color='red', linestyle='--', linewidth=2, label='600s Timeout Limit', alpha=0.7)

# Add value labels on bars
def add_labels(bars):
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}s',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

add_labels(bars1)
add_labels(bars2)
add_labels(bars3)

ax.set_xlabel('Video Length', fontsize=12, fontweight='bold')
ax.set_ylabel('Processing Time (seconds)', fontsize=12, fontweight='bold')
ax.set_title('GPU Processing Time Comparison\nWav2Lip Inference Performance',
             fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(video_lengths)
ax.legend(fontsize=11, loc='upper left')
ax.grid(axis='y', alpha=0.3)

# Add annotation
ax.text(2.35, 620, '⚠️ Timeout Risk', fontsize=10, color='red', fontweight='bold')

plt.tight_layout()
plt.savefig(output_dir / 'chart1_processing_time.png', dpi=300, bbox_inches='tight')
print(f"✅ Saved: {output_dir / 'chart1_processing_time.png'}")
plt.close()

# ============== Chart 2: Cost per Video Comparison ==============
fig, ax = plt.subplots(figsize=(12, 6))

bars1 = ax.bar(x - width, cost_per_video['T4'], width, label='T4', color=colors['T4'], alpha=0.8)
bars2 = ax.bar(x, cost_per_video['A10G'], width, label='A10G', color=colors['A10G'], alpha=0.8)
bars3 = ax.bar(x + width, cost_per_video['A100'], width, label='A100', color=colors['A100'], alpha=0.8)

# Add value labels on bars
def add_cost_labels(bars):
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'${height:.3f}',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

add_cost_labels(bars1)
add_cost_labels(bars2)
add_cost_labels(bars3)

ax.set_xlabel('Video Length', fontsize=12, fontweight='bold')
ax.set_ylabel('Cost per Video (USD)', fontsize=12, fontweight='bold')
ax.set_title('GPU Cost Comparison\nPer-Video Processing Cost',
             fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(video_lengths)
ax.legend(fontsize=11, loc='upper left')
ax.grid(axis='y', alpha=0.3)

# Add savings annotation
savings_1min = ((cost_per_video['A100'][0] - cost_per_video['T4'][0]) / cost_per_video['A100'][0]) * 100
ax.text(0, 0.045, f'T4: 78% cheaper\nthan A100',
        fontsize=10, color=colors['T4'], fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))

plt.tight_layout()
plt.savefig(output_dir / 'chart2_cost_comparison.png', dpi=300, bbox_inches='tight')
print(f"✅ Saved: {output_dir / 'chart2_cost_comparison.png'}")
plt.close()

# ============== Chart 3: Monthly Cost at Scale (1000 videos/month) ==============
fig, ax = plt.subplots(figsize=(12, 6))

monthly_cost = {
    'T4': [v * 1000 for v in cost_per_video['T4']],
    'A10G': [v * 1000 for v in cost_per_video['A10G']],
    'A100': [v * 1000 for v in cost_per_video['A100']]
}

bars1 = ax.bar(x - width, monthly_cost['T4'], width, label='T4', color=colors['T4'], alpha=0.8)
bars2 = ax.bar(x, monthly_cost['A10G'], width, label='A10G', color=colors['A10G'], alpha=0.8)
bars3 = ax.bar(x + width, monthly_cost['A100'], width, label='A100', color=colors['A100'], alpha=0.8)

# Add value labels
def add_monthly_labels(bars):
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'${height:.0f}',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

add_monthly_labels(bars1)
add_monthly_labels(bars2)
add_monthly_labels(bars3)

ax.set_xlabel('Video Length', fontsize=12, fontweight='bold')
ax.set_ylabel('Monthly Cost (USD)', fontsize=12, fontweight='bold')
ax.set_title('Monthly Cost at Scale\n1,000 Videos per Month',
             fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(video_lengths)
ax.legend(fontsize=11, loc='upper left')
ax.grid(axis='y', alpha=0.3)

# Add annual savings annotation
annual_savings = (monthly_cost['A100'][0] - monthly_cost['T4'][0]) * 12
ax.text(2.3, 450, f'Annual Savings:\n${annual_savings:,.0f}/year\n(T4 vs A100)',
        fontsize=11, color=colors['T4'], fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.8', facecolor='white', edgecolor=colors['T4'], linewidth=2))

plt.tight_layout()
plt.savefig(output_dir / 'chart3_monthly_cost.png', dpi=300, bbox_inches='tight')
print(f"✅ Saved: {output_dir / 'chart3_monthly_cost.png'}")
plt.close()

# ============== Chart 4: Cost-Performance Scatter Plot ==============
fig, ax = plt.subplots(figsize=(12, 8))

# Use 1-min video data for this comparison
gpus = ['T4', 'A10G', 'A100']
speeds = [processing_times['T4'][0], processing_times['A10G'][0], processing_times['A100'][0]]
costs = [cost_per_video['T4'][0], cost_per_video['A10G'][0], cost_per_video['A100'][0]]

# Create scatter plot
for i, gpu in enumerate(gpus):
    ax.scatter(speeds[i], costs[i], s=1000, alpha=0.6, color=colors[gpu],
               edgecolors='black', linewidths=2, label=gpu)
    ax.annotate(gpu, (speeds[i], costs[i]), fontsize=14, fontweight='bold',
                ha='center', va='center')

# Add arrows and annotations
ax.annotate('', xy=(40, 0.044), xytext=(58, 0.044),
            arrowprops=dict(arrowstyle='<->', color='gray', lw=2))
ax.text(49, 0.046, '31% faster', fontsize=10, ha='center', color='gray', fontweight='bold')

ax.annotate('', xy=(58, 0.0097), xytext=(58, 0.044),
            arrowprops=dict(arrowstyle='<->', color='gray', lw=2))
ax.text(62, 0.027, '78% cheaper', fontsize=10, ha='left', color='gray', fontweight='bold',
        rotation=90, va='center')

# Add optimal zone
ax.axvspan(50, 60, alpha=0.1, color='green', label='Optimal Zone (Fast + Cheap)')

ax.set_xlabel('Processing Time (seconds) - Lower is Better ➡️', fontsize=12, fontweight='bold')
ax.set_ylabel('Cost per Video (USD) - Lower is Better ⬇️', fontsize=12, fontweight='bold')
ax.set_title('Cost-Performance Trade-off Analysis\n1-Minute Video Processing',
             fontsize=14, fontweight='bold', pad=20)
ax.legend(fontsize=11, loc='upper right')
ax.grid(True, alpha=0.3)
ax.invert_xaxis()  # Invert so faster is to the right

# Add decision box
decision_text = "✅ DECISION: T4 GPU\n• Best cost-performance ratio\n• 78% cheaper than A100\n• Adequate speed for batch workflows"
ax.text(0.02, 0.98, decision_text, transform=ax.transAxes,
        fontsize=11, verticalalignment='top',
        bbox=dict(boxstyle='round,pad=1', facecolor='lightgreen', alpha=0.8, edgecolor='green', linewidth=2))

plt.tight_layout()
plt.savefig(output_dir / 'chart4_cost_performance_tradeoff.png', dpi=300, bbox_inches='tight')
print(f"✅ Saved: {output_dir / 'chart4_cost_performance_tradeoff.png'}")
plt.close()

# ============== Chart 5: Throughput Comparison ==============
fig, ax = plt.subplots(figsize=(12, 6))

throughput = {
    'T4': [3600/58, 3600/290, 3600/580],      # videos per hour
    'A10G': [3600/59, 3600/295, 3600/590],
    'A100': [3600/40, 3600/200, 3600/400]
}

bars1 = ax.bar(x - width, throughput['T4'], width, label='T4', color=colors['T4'], alpha=0.8)
bars2 = ax.bar(x, throughput['A10G'], width, label='A10G', color=colors['A10G'], alpha=0.8)
bars3 = ax.bar(x + width, throughput['A100'], width, label='A100', color=colors['A100'], alpha=0.8)

# Add value labels
def add_throughput_labels(bars):
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

add_throughput_labels(bars1)
add_throughput_labels(bars2)
add_throughput_labels(bars3)

ax.set_xlabel('Video Length', fontsize=12, fontweight='bold')
ax.set_ylabel('Videos Processed per Hour', fontsize=12, fontweight='bold')
ax.set_title('GPU Throughput Comparison\nVideos Processed per Hour per GPU',
             fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(video_lengths)
ax.legend(fontsize=11, loc='upper right')
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig(output_dir / 'chart5_throughput.png', dpi=300, bbox_inches='tight')
print(f"✅ Saved: {output_dir / 'chart5_throughput.png'}")
plt.close()

# ============== Chart 6: ROI vs Manual Dubbing ==============
fig, ax = plt.subplots(figsize=(12, 8))

# Manual dubbing cost vs automated
manual_cost_per_min = 1200
automated_cost_t4 = [0.0097, 0.048, 0.097]
video_lengths_num = [1, 5, 10]
manual_costs = [manual_cost_per_min * length for length in video_lengths_num]

x_roi = np.arange(len(video_lengths))
width_roi = 0.35

bars_manual = ax.bar(x_roi - width_roi/2, manual_costs, width_roi,
                     label='Manual Dubbing', color='#e74c3c', alpha=0.8)
bars_auto = ax.bar(x_roi + width_roi/2, automated_cost_t4, width_roi,
                   label='Automated (T4)', color='#2ecc71', alpha=0.8)

# Add value labels
for bar in bars_manual:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'${height:,.0f}',
            ha='center', va='bottom', fontsize=10, fontweight='bold')

for bar in bars_auto:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 100,
            f'${height:.2f}',
            ha='center', va='bottom', fontsize=10, fontweight='bold', color='green')

ax.set_xlabel('Video Length (minutes)', fontsize=12, fontweight='bold')
ax.set_ylabel('Cost per Video (USD) - Log Scale', fontsize=12, fontweight='bold')
ax.set_title('ROI Analysis: Manual Dubbing vs Automated Wav2Lip\nCost Comparison (Log Scale)',
             fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x_roi)
ax.set_xticklabels(video_lengths)
ax.set_yscale('log')
ax.legend(fontsize=12, loc='upper left')
ax.grid(True, alpha=0.3, which='both')

# Add ROI text
roi_text = f"💰 ROI for 1-min video:\n{manual_costs[0] / automated_cost_t4[0]:,.0f}x cost reduction\n\n99.999% savings"
ax.text(0.98, 0.95, roi_text, transform=ax.transAxes,
        fontsize=12, verticalalignment='top', horizontalalignment='right',
        bbox=dict(boxstyle='round,pad=1', facecolor='lightgreen', alpha=0.9, edgecolor='green', linewidth=2))

plt.tight_layout()
plt.savefig(output_dir / 'chart6_roi_comparison.png', dpi=300, bbox_inches='tight')
print(f"✅ Saved: {output_dir / 'chart6_roi_comparison.png'}")
plt.close()

print(f"\n✅ All charts generated successfully in '{output_dir}/' directory")
print(f"\nGenerated files:")
print(f"  1. chart1_processing_time.png - Processing time comparison")
print(f"  2. chart2_cost_comparison.png - Cost per video")
print(f"  3. chart3_monthly_cost.png - Monthly costs at scale")
print(f"  4. chart4_cost_performance_tradeoff.png - Scatter plot analysis")
print(f"  5. chart5_throughput.png - Videos per hour")
print(f"  6. chart6_roi_comparison.png - ROI vs manual dubbing")
