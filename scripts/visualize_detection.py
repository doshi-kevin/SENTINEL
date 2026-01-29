"""
SENTINEL-Z Detection Visualization Suite
========================================
Generates comprehensive visualizations for demo and analysis.

Outputs:
1. confusion_matrix.png - Shows TP, FP, TN, FN at optimal threshold
2. roc_curve.png - ROC curve with AUC score
3. score_distributions.png - Attack vs Benign score histograms
4. detection_timeline.png - All attacks with detection status
5. precision_recall_tradeoff.png - Precision vs Recall at different thresholds
6. attack_detection_summary.png - Which attacks we caught vs missed
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import roc_curve, auc, confusion_matrix, precision_recall_curve
import os

# Configuration
OUTPUT_DIR = r'c:\SENTINEL\scripts\visualizations'
DATA_PATH = r'c:\SENTINEL\data\model_ready\detection\phase4_scores.csv'

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Set visual style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 11

# Color palette
COLORS = {
    'attack': '#e74c3c',      # Red
    'benign': '#3498db',      # Blue
    'detected': '#27ae60',    # Green
    'missed': '#e74c3c',      # Red
    'false_alarm': '#f39c12', # Orange
    'true_negative': '#95a5a6' # Gray
}

def load_data():
    """Load and prepare the detection data."""
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} windows: {(df['label']==1).sum()} attacks, {(df['label']==0).sum()} benign")
    return df

def find_optimal_threshold(df, target_fpr=0.04):
    """Find threshold that achieves approximately target FPR."""
    benign_scores = df[df['label'] == 0]['fused_score']
    # Find score at (1-target_fpr) percentile of benign
    threshold = benign_scores.quantile(1 - target_fpr)
    return threshold

def plot_confusion_matrix(df, threshold, output_path):
    """Plot confusion matrix at given threshold."""
    y_true = df['label'].values
    y_pred = (df['fused_score'] >= threshold).astype(int).values

    cm = confusion_matrix(y_true, y_pred)

    fig, ax = plt.subplots(figsize=(8, 6))

    # Custom labels
    labels = np.array([['True Negative\n(Correctly Ignored)', 'False Positive\n(False Alarm)'],
                       ['False Negative\n(Missed Attack)', 'True Positive\n(Detected Attack)']])

    # Plot heatmap
    sns.heatmap(cm, annot=False, fmt='d', cmap='Blues', ax=ax,
                xticklabels=['Predicted Benign', 'Predicted Attack'],
                yticklabels=['Actual Benign', 'Actual Attack'])

    # Add custom annotations
    for i in range(2):
        for j in range(2):
            color = 'white' if cm[i, j] > cm.max() / 2 else 'black'
            ax.text(j + 0.5, i + 0.35, f'{cm[i, j]:,}',
                   ha='center', va='center', fontsize=20, fontweight='bold', color=color)
            ax.text(j + 0.5, i + 0.65, labels[i, j],
                   ha='center', va='center', fontsize=9, color=color)

    # Calculate metrics
    tn, fp, fn, tp = cm.ravel()
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    ax.set_title(f'Confusion Matrix @ Threshold = {threshold:.1f}\n'
                 f'Precision: {precision:.1%} | Recall: {recall:.1%} | FPR: {fpr:.1%}',
                 fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")
    return precision, recall, fpr

def plot_roc_curve(df, output_path):
    """Plot ROC curve with AUC."""
    y_true = df['label'].values
    y_scores = df['fused_score'].values

    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    roc_auc = auc(fpr, tpr)

    fig, ax = plt.subplots(figsize=(8, 8))

    # Plot ROC curve
    ax.plot(fpr, tpr, color=COLORS['attack'], lw=3,
            label=f'SENTINEL-Z (AUC = {roc_auc:.4f})')

    # Plot random baseline
    ax.plot([0, 1], [0, 1], color='gray', lw=2, linestyle='--', label='Random Guess (AUC = 0.5)')

    # Fill area under curve
    ax.fill_between(fpr, tpr, alpha=0.2, color=COLORS['attack'])

    # Mark key operating points
    target_fprs = [0.01, 0.04, 0.10, 0.20]
    for target_fpr in target_fprs:
        idx = np.argmin(np.abs(fpr - target_fpr))
        ax.scatter(fpr[idx], tpr[idx], s=100, zorder=5, edgecolors='black', linewidth=2)
        ax.annotate(f'FPR={fpr[idx]:.0%}\nTPR={tpr[idx]:.0%}',
                   xy=(fpr[idx], tpr[idx]), xytext=(fpr[idx]+0.05, tpr[idx]-0.08),
                   fontsize=9, ha='left')

    ax.set_xlabel('False Positive Rate (FPR)', fontsize=12)
    ax.set_ylabel('True Positive Rate (Recall)', fontsize=12)
    ax.set_title('ROC Curve: SENTINEL-Z Attack Detection\n'
                 'Higher curve = Better separation of attacks from benign',
                 fontsize=14, fontweight='bold')
    ax.legend(loc='lower right', fontsize=11)
    ax.set_xlim([-0.02, 1.02])
    ax.set_ylim([-0.02, 1.02])
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")
    return roc_auc

def plot_score_distributions(df, threshold, output_path):
    """Plot overlapping histograms of attack vs benign scores."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    attack_scores = df[df['label'] == 1]['fused_score']
    benign_scores = df[df['label'] == 0]['fused_score']

    # Left plot: Histogram
    ax1 = axes[0]
    bins = np.linspace(10, 45, 50)

    ax1.hist(benign_scores, bins=bins, alpha=0.6, color=COLORS['benign'],
             label=f'Benign (n={len(benign_scores):,})', density=True)
    ax1.hist(attack_scores, bins=bins, alpha=0.8, color=COLORS['attack'],
             label=f'Attacks (n={len(attack_scores)})', density=True)

    ax1.axvline(x=threshold, color='black', linestyle='--', lw=2,
                label=f'Threshold = {threshold:.1f}')

    # Shade regions
    ax1.axvspan(threshold, 45, alpha=0.1, color='red', label='Flagged Zone')

    ax1.set_xlabel('Fused Risk Score', fontsize=12)
    ax1.set_ylabel('Density', fontsize=12)
    ax1.set_title('Score Distribution: Attacks vs Benign', fontsize=13, fontweight='bold')
    ax1.legend(loc='upper right')
    ax1.set_xlim(10, 45)

    # Right plot: KDE with overlap visualization
    ax2 = axes[1]

    sns.kdeplot(data=benign_scores, ax=ax2, color=COLORS['benign'],
                fill=True, alpha=0.4, label='Benign', linewidth=2)
    sns.kdeplot(data=attack_scores, ax=ax2, color=COLORS['attack'],
                fill=True, alpha=0.4, label='Attacks', linewidth=2)

    ax2.axvline(x=threshold, color='black', linestyle='--', lw=2)

    # Add annotations
    ax2.annotate(f'Attack Mean: {attack_scores.mean():.1f}',
                xy=(attack_scores.mean(), 0.15), fontsize=10, color=COLORS['attack'],
                fontweight='bold')
    ax2.annotate(f'Benign Mean: {benign_scores.mean():.1f}',
                xy=(benign_scores.mean(), 0.25), fontsize=10, color=COLORS['benign'],
                fontweight='bold')

    ax2.set_xlabel('Fused Risk Score', fontsize=12)
    ax2.set_ylabel('Density', fontsize=12)
    ax2.set_title('Kernel Density Estimation (KDE)', fontsize=13, fontweight='bold')
    ax2.legend(loc='upper right')
    ax2.set_xlim(10, 35)

    plt.suptitle('SENTINEL-Z: How Well Can We Separate Attacks from Normal Activity?',
                 fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

def plot_detection_timeline(df, threshold, output_path):
    """Plot timeline showing all windows with attack detection status."""
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={'height_ratios': [3, 1]})

    # Top plot: Score timeline with detections
    ax1 = axes[0]

    # Plot all scores as a line
    ax1.plot(df['window_id'], df['fused_score'], color='#bdc3c7', lw=0.5, alpha=0.7,
             label='All Windows')

    # Highlight attack windows
    attacks = df[df['label'] == 1]
    detected = attacks[attacks['fused_score'] >= threshold]
    missed = attacks[attacks['fused_score'] < threshold]

    # Plot detected attacks (green)
    ax1.scatter(detected['window_id'], detected['fused_score'],
               color=COLORS['detected'], s=80, marker='^', edgecolors='black', linewidth=1,
               label=f'Detected Attacks ({len(detected)})', zorder=5)

    # Plot missed attacks (red)
    ax1.scatter(missed['window_id'], missed['fused_score'],
               color=COLORS['missed'], s=80, marker='v', edgecolors='black', linewidth=1,
               label=f'Missed Attacks ({len(missed)})', zorder=5)

    # Plot false positives (orange)
    benign_flagged = df[(df['label'] == 0) & (df['fused_score'] >= threshold)]
    ax1.scatter(benign_flagged['window_id'], benign_flagged['fused_score'],
               color=COLORS['false_alarm'], s=30, marker='x', alpha=0.5,
               label=f'False Alarms ({len(benign_flagged)})', zorder=4)

    # Threshold line
    ax1.axhline(y=threshold, color='black', linestyle='--', lw=2,
                label=f'Threshold = {threshold:.1f}')

    ax1.set_ylabel('Fused Risk Score', fontsize=12)
    ax1.set_title('SENTINEL-Z Detection Timeline: Every Attack Shown',
                  fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', ncol=2)
    ax1.set_xlim(0, len(df))
    ax1.set_ylim(10, 45)
    ax1.grid(True, alpha=0.3)

    # Bottom plot: Ground truth bar
    ax2 = axes[1]

    # Create colored bar for each window
    colors = []
    for _, row in df.iterrows():
        if row['label'] == 1:
            if row['fused_score'] >= threshold:
                colors.append(COLORS['detected'])  # Detected attack
            else:
                colors.append(COLORS['missed'])    # Missed attack
        else:
            if row['fused_score'] >= threshold:
                colors.append(COLORS['false_alarm'])  # False positive
            else:
                colors.append(COLORS['true_negative'])  # True negative

    # Plot as colored segments
    ax2.scatter(df['window_id'], [1]*len(df), c=colors, s=2, marker='|')

    # Create legend patches
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS['detected'], label='Detected Attack (TP)'),
        Patch(facecolor=COLORS['missed'], label='Missed Attack (FN)'),
        Patch(facecolor=COLORS['false_alarm'], label='False Alarm (FP)'),
        Patch(facecolor=COLORS['true_negative'], label='Correctly Ignored (TN)')
    ]
    ax2.legend(handles=legend_elements, loc='center', ncol=4, frameon=False)

    ax2.set_xlabel('Window ID (Time)', fontsize=12)
    ax2.set_ylabel('')
    ax2.set_yticks([])
    ax2.set_xlim(0, len(df))
    ax2.set_title('Ground Truth Classification', fontsize=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

def plot_precision_recall_tradeoff(df, output_path):
    """Plot precision vs recall at different thresholds."""
    y_true = df['label'].values
    y_scores = df['fused_score'].values

    # Calculate precision-recall curve
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_scores)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left plot: Precision-Recall curve
    ax1 = axes[0]
    ax1.plot(recalls, precisions, color=COLORS['attack'], lw=3)
    ax1.fill_between(recalls, precisions, alpha=0.2, color=COLORS['attack'])

    # Mark key thresholds
    key_thresholds = [19, 20, 21, 22, 23, 24, 25]
    for t in key_thresholds:
        idx = np.argmin(np.abs(thresholds - t))
        ax1.scatter(recalls[idx], precisions[idx], s=100, zorder=5, edgecolors='black', linewidth=2)
        ax1.annotate(f't={t}', xy=(recalls[idx], precisions[idx]),
                    xytext=(recalls[idx]+0.03, precisions[idx]+0.01), fontsize=9)

    ax1.set_xlabel('Recall (% of attacks caught)', fontsize=12)
    ax1.set_ylabel('Precision (% of alerts that are real)', fontsize=12)
    ax1.set_title('Precision-Recall Tradeoff\nHigher = Better', fontsize=13, fontweight='bold')
    ax1.set_xlim([0, 1])
    ax1.set_ylim([0, 0.25])
    ax1.grid(True, alpha=0.3)

    # Right plot: Threshold vs Metrics
    ax2 = axes[1]

    test_thresholds = np.arange(17, 28, 0.5)
    precisions_list = []
    recalls_list = []
    fprs_list = []

    for t in test_thresholds:
        y_pred = (y_scores >= t).astype(int)
        tp = ((y_pred == 1) & (y_true == 1)).sum()
        fp = ((y_pred == 1) & (y_true == 0)).sum()
        fn = ((y_pred == 0) & (y_true == 1)).sum()
        tn = ((y_pred == 0) & (y_true == 0)).sum()

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

        precisions_list.append(precision)
        recalls_list.append(recall)
        fprs_list.append(fpr)

    ax2.plot(test_thresholds, recalls_list, color=COLORS['detected'], lw=2,
             label='Recall (Attacks Caught)', marker='o', markersize=4)
    ax2.plot(test_thresholds, precisions_list, color=COLORS['attack'], lw=2,
             label='Precision', marker='s', markersize=4)
    ax2.plot(test_thresholds, fprs_list, color=COLORS['false_alarm'], lw=2,
             label='False Positive Rate', marker='^', markersize=4)

    ax2.set_xlabel('Detection Threshold', fontsize=12)
    ax2.set_ylabel('Metric Value', fontsize=12)
    ax2.set_title('How Threshold Affects Detection\nChoose based on your tolerance for false alarms',
                  fontsize=13, fontweight='bold')
    ax2.legend(loc='center right')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(17, 28)
    ax2.set_ylim(0, 1)

    plt.suptitle('SENTINEL-Z: Finding the Right Balance', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

def plot_attack_summary(df, threshold, output_path):
    """Create a summary visualization of attack detection."""
    attacks = df[df['label'] == 1].copy()
    attacks['detected'] = attacks['fused_score'] >= threshold
    attacks = attacks.sort_values('fused_score', ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(14, 8))

    # Left: Bar chart of all attacks sorted by score
    ax1 = axes[0]

    colors = [COLORS['detected'] if d else COLORS['missed'] for d in attacks['detected']]
    bars = ax1.barh(range(len(attacks)), attacks['fused_score'], color=colors, edgecolor='white')

    ax1.axvline(x=threshold, color='black', linestyle='--', lw=2, label=f'Threshold = {threshold:.1f}')

    ax1.set_xlabel('Fused Risk Score', fontsize=12)
    ax1.set_ylabel('Attack Window (sorted by score)', fontsize=12)
    ax1.set_title(f'All {len(attacks)} Attack Windows\n'
                  f'Detected: {attacks["detected"].sum()} | Missed: {(~attacks["detected"]).sum()}',
                  fontsize=13, fontweight='bold')

    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS['detected'], label='Detected'),
        Patch(facecolor=COLORS['missed'], label='Missed')
    ]
    ax1.legend(handles=legend_elements, loc='lower right')
    ax1.set_xlim(15, 30)

    # Right: Pie chart summary
    ax2 = axes[1]

    detected_count = attacks['detected'].sum()
    missed_count = (~attacks['detected']).sum()

    benign = df[df['label'] == 0]
    false_alarms = (benign['fused_score'] >= threshold).sum()
    true_negatives = (benign['fused_score'] < threshold).sum()

    # Main pie: Detection outcome
    sizes = [detected_count, missed_count]
    labels = [f'Detected\n({detected_count})', f'Missed\n({missed_count})']
    colors_pie = [COLORS['detected'], COLORS['missed']]
    explode = (0.05, 0)

    wedges, texts, autotexts = ax2.pie(sizes, labels=labels, colors=colors_pie,
                                        explode=explode, autopct='%1.1f%%',
                                        shadow=True, startangle=90,
                                        textprops={'fontsize': 12})

    ax2.set_title(f'Attack Detection Rate\n'
                  f'Recall = {detected_count}/{len(attacks)} = {detected_count/len(attacks)*100:.1f}%',
                  fontsize=13, fontweight='bold')

    # Add text summary below
    summary_text = (f"Detection Summary @ Threshold {threshold:.1f}:\n"
                   f"  True Positives: {detected_count:,} (attacks caught)\n"
                   f"  False Negatives: {missed_count:,} (attacks missed)\n"
                   f"  False Positives: {false_alarms:,} (false alarms)\n"
                   f"  True Negatives: {true_negatives:,} (correctly ignored)")

    fig.text(0.75, 0.15, summary_text, fontsize=11, family='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
             transform=fig.transFigure, ha='center')

    plt.suptitle('SENTINEL-Z: Attack Detection Summary', fontsize=15, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

def plot_multi_threshold_comparison(df, output_path):
    """Show detection at multiple thresholds for demo flexibility."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    thresholds = [20, 21, 22, 23]

    for ax, thresh in zip(axes.flatten(), thresholds):
        attacks = df[df['label'] == 1]
        benign = df[df['label'] == 0]

        detected = attacks[attacks['fused_score'] >= thresh]
        missed = attacks[attacks['fused_score'] < thresh]
        false_alarms = benign[benign['fused_score'] >= thresh]

        # Calculate metrics
        tp = len(detected)
        fp = len(false_alarms)
        fn = len(missed)
        tn = len(benign) - fp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

        # Create stacked bar
        categories = ['Attacks\n(n=85)', 'Benign\n(n=5,966)']
        detected_vals = [tp, 0]
        missed_vals = [fn, 0]
        false_alarm_vals = [0, fp]
        true_neg_vals = [0, tn]

        x = np.arange(len(categories))
        width = 0.6

        ax.bar(x, detected_vals, width, label='Detected (TP)', color=COLORS['detected'])
        ax.bar(x, missed_vals, width, bottom=detected_vals, label='Missed (FN)', color=COLORS['missed'])
        ax.bar(x, false_alarm_vals, width, label='False Alarm (FP)', color=COLORS['false_alarm'])
        ax.bar(x, true_neg_vals, width, bottom=false_alarm_vals, label='Correct (TN)', color=COLORS['true_negative'])

        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.set_ylabel('Count')
        ax.set_title(f'Threshold = {thresh}\n'
                     f'Recall: {recall:.1%} | Precision: {precision:.1%} | FPR: {fpr:.1%}',
                     fontsize=11, fontweight='bold')

        if ax == axes[0, 0]:
            ax.legend(loc='upper right', fontsize=8)

    plt.suptitle('SENTINEL-Z: Detection at Different Thresholds\n'
                 'Choose based on acceptable false alarm rate',
                 fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

def main():
    """Generate all visualizations."""
    print("=" * 60)
    print("SENTINEL-Z Visualization Suite")
    print("=" * 60)

    # Load data
    df = load_data()

    # Find optimal threshold (~4% FPR based on previous analysis)
    threshold = 23.0  # Based on our analysis: good balance of recall and precision
    print(f"\nUsing threshold: {threshold}")

    # Generate all plots
    print("\n--- Generating Visualizations ---\n")

    # 1. ROC Curve
    roc_auc = plot_roc_curve(df, os.path.join(OUTPUT_DIR, 'roc_curve.png'))
    print(f"   ROC-AUC: {roc_auc:.4f}")

    # 2. Confusion Matrix
    precision, recall, fpr = plot_confusion_matrix(df, threshold,
                                                    os.path.join(OUTPUT_DIR, 'confusion_matrix.png'))
    print(f"   Precision: {precision:.2%}, Recall: {recall:.2%}, FPR: {fpr:.2%}")

    # 3. Score Distributions
    plot_score_distributions(df, threshold, os.path.join(OUTPUT_DIR, 'score_distributions.png'))

    # 4. Detection Timeline
    plot_detection_timeline(df, threshold, os.path.join(OUTPUT_DIR, 'detection_timeline.png'))

    # 5. Precision-Recall Tradeoff
    plot_precision_recall_tradeoff(df, os.path.join(OUTPUT_DIR, 'precision_recall_tradeoff.png'))

    # 6. Attack Summary
    plot_attack_summary(df, threshold, os.path.join(OUTPUT_DIR, 'attack_summary.png'))

    # 7. Multi-threshold comparison
    plot_multi_threshold_comparison(df, os.path.join(OUTPUT_DIR, 'multi_threshold_comparison.png'))

    print("\n" + "=" * 60)
    print(f"All visualizations saved to: {OUTPUT_DIR}")
    print("=" * 60)

    # Print summary for README
    print("\n--- Summary for README ---")
    print(f"""
At Threshold = {threshold}:
- True Positives (Attacks Caught): {int(recall * 85)}
- False Negatives (Attacks Missed): {int((1-recall) * 85)}
- False Positives (False Alarms): {int(fpr * 5966)}
- Precision: {precision:.2%}
- Recall: {recall:.2%}
- False Positive Rate: {fpr:.2%}
- ROC-AUC: {roc_auc:.4f}
""")

if __name__ == '__main__':
    main()
