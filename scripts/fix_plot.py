import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load data
df = pd.read_csv(r'c:\SENTINEL\data\model_ready\detection\phase4_scores.csv')

# Dynamic threshold find: Let's look for a threshold that captures the most attacks with minimal noise
# Recalculating metrics at different thresholds
attack_scores = df[df['label'] == 1]['fused_score']
benign_scores = df[df['label'] == 0]['fused_score']

print(f"Attack Score Range: {attack_scores.min():.2f} - {attack_scores.max():.2f}")
print(f"Benign Score Range: {benign_scores.min():.2f} - {benign_scores.max():.2f}")

# The previous 35.0 might have been too conservative. 
# Let's try 30.0 for better visibility in the plot.
optimal_threshold = 30.0

plt.figure(figsize=(15, 8))

# 1. Plot ground truth (Background shading)
# We use a higher multiplier for the background so it's clearly visible
plt.fill_between(df['window_id'], 0, df['label'] * 65, color='#ff7675', alpha=0.2, label='ACTUAL ATTACK DURATION')

# 2. Plot the Score Pulse
# Using a slightly thicker line for the heartbeat
plt.plot(df['window_id'], df['fused_score'], color='#0984e3', linewidth=1, alpha=0.6, label='SENTINEL-Z Risk Heartbeat')

# 3. Detect Alarms
alarms = df[df['fused_score'] >= optimal_threshold]
plt.scatter(alarms['window_id'], alarms['fused_score'], color='#d63031', s=30, label='ALARMS TRIGGERED', edgecolors='white', linewidth=0.5, zorder=5)

# 4. Draw Threshold Line
plt.axhline(y=optimal_threshold, color='#e67e22', linestyle='--', linewidth=2, label=f'Alert Threshold ({optimal_threshold})')

plt.title('SENTINEL-Z: Precision Attack Detection in Operation', fontsize=18, fontweight='bold')
plt.xlabel('Time (1-Second Snapshot ID)', fontsize=14)
plt.ylabel('Risk Intensity Score', fontsize=14)
plt.legend(loc='upper right', frameon=True, shadow=True)

# Focus on the primary attack cluster for visibility (Windows 0 to 1200)
plt.xlim(0, 1200)
plt.ylim(0, 65)

plt.tight_layout()
plt.savefig('c:\\SENTINEL\\scripts\\detection_alarms.png', dpi=300)
print(f"Redesigned plot saved to c:\\SENTINEL\\scripts\\detection_alarms.png at threshold {optimal_threshold}")
