import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# Set visual style
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams['figure.figsize'] = [10, 6]
plt.rcParams['font.size'] = 12

# 1. Performance Metrics Comparison (Phase 3 vs Phase 4)
metrics = {
    'Metric': ['ROC-AUC', 'F1-Score', 'Precision', 'Recall', 'FPR'],
    'Phase 3 (Baseline)': [0.6572, 0.0458, 0.0261, 0.1882, 0.1001],
    'Phase 4 (Fused)': [0.8628, 0.1163, 0.0772, 0.2353, 0.0401]
}

df_metrics = pd.DataFrame(metrics).melt(id_vars='Metric', var_name='Phase', value_name='Value')

plt.figure(figsize=(12, 7))
ax = sns.barplot(data=df_metrics, x='Metric', y='Value', hue='Phase')
plt.title('Performance Leap: Phase 3 vs Phase 4', fontsize=16, fontweight='bold')
plt.ylabel('Score (Higher is better, except FPR)', fontsize=13)
plt.ylim(0, 1.0)

# Add value labels
for p in ax.patches:
    ax.annotate(format(p.get_height(), '.3f'), 
                   (p.get_x() + p.get_width() / 2., p.get_height()), 
                   ha = 'center', va = 'center', 
                   xytext = (0, 9), 
                   textcoords = 'offset points')

plt.savefig('performance_comparison.png', dpi=300, bbox_inches='tight')
print("Saved performance_comparison.png")

# 2. Score Distribution (Benign vs Anomaly)
scores_df = pd.read_csv(r'c:\SENTINEL\data\model_ready\detection\phase4_scores.csv')

plt.figure(figsize=(12, 6))
sns.kdeplot(data=scores_df[scores_df['label'] == 0], x='fused_score', label='Benign Windows', fill=True, alpha=0.3)
sns.kdeplot(data=scores_df[scores_df['label'] == 1], x='fused_score', label='Attack Windows', fill=True, alpha=0.3)
plt.title('Fused Score Distribution: Attacks vs. Benign Activity', fontsize=16, fontweight='bold')
plt.xlabel('Fused Risk Score', fontsize=14)
plt.ylabel('Density', fontsize=14)
plt.legend()
plt.savefig('score_distribution.png', dpi=300, bbox_inches='tight')
print("Saved score_distribution.png")

# 3. Detection Timeline: Signal vs. Noise (Focus on Attack Windows 50-150)
subset_df = scores_df[(scores_df['window_id'] >= 50) & (scores_df['window_id'] <= 150)].copy()

fig, ax1 = plt.subplots(figsize=(14, 7))

# Plot Fused Score
ax1.plot(subset_df['window_id'], subset_df['fused_score'], color='#3498db', label='Fused Risk Score', linewidth=2)
ax1.set_xlabel('Time (Window ID)', fontsize=13)
ax1.set_ylabel('Risk Score', color='#3498db', fontsize=13)
ax1.tick_params(axis='y', labelcolor='#3498db')

# Plot Ground Truth (Shaded Areas)
ax2 = ax1.twinx()
ax2.fill_between(subset_df['window_id'], 0, subset_df['label'], color='#e74c3c', alpha=0.2, label='Actual Attack (Ground Truth)')
ax2.set_ylabel('Ground Truth (0=Benign, 1=Attack)', color='#e74c3c', fontsize=13)
ax2.set_yticks([0, 1])
ax2.tick_params(axis='y', labelcolor='#e74c3c')

plt.title('Detection Timeline: Score Spikes vs. Actual Attack Windows', fontsize=16, fontweight='bold')
fig.tight_layout()
plt.savefig('attack_timeline.png', dpi=300, bbox_inches='tight')
print("Saved attack_timeline.png")

# 4. Fusion Component Weights (Conceptual Breakdown)
# Based on the formula: 15*unknown + 0.2*structural + 1.0*size + 3*network + 2*density
weights = {
    'Unknown Subjects': 15.0,
    'Network Activity': 3.0,
    'Graph Connectivity': 2.0,
    'Window Size (Nodes)': 1.0,
    'Phase 3 Structural': 0.2
}

plt.figure(figsize=(10, 8))
plt.pie(weights.values(), labels=weights.keys(), autopct='%1.1f%%', 
        colors=['#e74c3c', '#3498db', '#f1c40f', '#2ecc71', '#95a5a6'],
        startangle=140, explode=(0.1, 0, 0, 0, 0))
plt.title('Fusion Logic: Contribution of Different Risk Signals', fontsize=16, fontweight='bold')
plt.savefig('fusion_weights.png', dpi=300, bbox_inches='tight')
print("Saved fusion_weights.png")

# 5. Alarm Plot: When and How We Detect Attacks
# We'll plot the threshold-based alert vs the real attack duration
# Threshold selected for ~4% FPR (Phase 4 result)
threshold = 35.0 

plt.figure(figsize=(15, 8))

# 1. Fill ground truth area
plt.fill_between(scores_df['window_id'], 0, scores_df['label'] * 60, color='#e74c3c', alpha=0.15, label='Actual Attack Duration')

# 2. Scatter detection points (Alarms)
alarms_mask = scores_df['fused_score'] >= threshold
plt.scatter(scores_df.loc[alarms_mask, 'window_id'], 
            scores_df.loc[alarms_mask, 'fused_score'], 
            color='#c0392b', s=20, alpha=0.6, label='SENTINEL-Z Alarms (Detection)')

# 3. Plot the trace of the score
plt.plot(scores_df['window_id'], scores_df['fused_score'], color='#2980b9', linewidth=0.5, alpha=0.4, label='Risk Score Heartbeat')

# 4. Draw the alert threshold
plt.axhline(y=threshold, color='#e67e22', linestyle='--', linewidth=2, label='Alert Threshold')

plt.title('How SENTINEL-Z Detects Attacks: Timing & Signal Strength', fontsize=18, fontweight='bold')
plt.xlabel('Operation Time (Window Snapshots)', fontsize=14)
plt.ylabel('Risk Score Intensity', fontsize=14)
plt.legend(loc='upper right', frameon=True, shadow=True)
plt.grid(True, alpha=0.3)

# Zoom into the most active attack area for clarity
plt.xlim(0, 1000) 
plt.ylim(0, 65)

plt.savefig('detection_alarms.png', dpi=300, bbox_inches='tight')
print("Saved detection_alarms.png")

# 6. Project Evolution Plot (Cumulative Accuracy)
phases = ['Phase 1', 'Phase 2', 'Phase 3', 'Phase 4']
desc = ['Data Foundations', 'Graph Construction', 'Structural Detection', 'Semantic Fusion']
auc_progression = [0.0, 0.0, 0.65, 0.86] # Placeholder for 1&2 as they weren't models

plt.figure(figsize=(10, 5))
plt.plot(phases, auc_progression, marker='o', linestyle='-', linewidth=3, markersize=10, color='#2ecc71')
plt.fill_between(phases, auc_progression, color='#2ecc71', alpha=0.2)
plt.title('Project Evolution: Detection Performance Over Time', fontsize=16, fontweight='bold')
plt.ylabel('Detection Accuracy (AUC)', fontsize=13)
plt.ylim(0, 1.0)
for i, txt in enumerate(desc):
    plt.annotate(txt, (phases[i], auc_progression[i]), textcoords="offset points", xytext=(0,10), ha='center', fontweight='bold')

plt.savefig('project_evolution.png', dpi=300, bbox_inches='tight')
print("Saved project_evolution.png")
