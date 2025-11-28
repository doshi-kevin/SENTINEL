"""
Simple Data Exploration - Get to Know Your Data
This creates easy-to-understand visualizations
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from pathlib import Path

# Set style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (14, 8)

# Create output directory
output_dir = Path('data/processed/analysis/')
output_dir.mkdir(parents=True, exist_ok=True)

print("="*70)
print("📊 SENTINEL Data Exploration")
print("="*70)

# Load the data
print("\n📥 Loading data...")
events_df = pd.read_csv('data/processed/events.csv')
subjects_df = pd.read_csv('data/processed/subjects.csv')
network_df = pd.read_csv('data/processed/network.csv')

print(f"✅ Loaded {len(events_df):,} events")
print(f"✅ Loaded {len(subjects_df):,} subjects")
print(f"✅ Loaded {len(network_df):,} network connections")

# Convert timestamps
events_df['timestamp'] = pd.to_datetime(events_df['timestamp'])

# ============================================================================
# 1. EVENT TYPE DISTRIBUTION
# ============================================================================
print("\n" + "="*70)
print("1️⃣  EVENT TYPE DISTRIBUTION")
print("="*70)

event_counts = events_df['type'].value_counts()
print(f"\nTop 10 event types:")
for i, (etype, count) in enumerate(event_counts.head(10).items(), 1):
    percentage = (count / len(events_df)) * 100
    print(f"   {i:2d}. {etype:40s}: {count:8,} ({percentage:5.1f}%)")

# Plot
plt.figure(figsize=(12, 6))
event_counts.head(15).plot(kind='barh', color='steelblue')
plt.title('Top 15 Event Types', fontsize=16, fontweight='bold')
plt.xlabel('Count', fontsize=12)
plt.ylabel('Event Type', fontsize=12)
plt.tight_layout()
plt.savefig(output_dir / '1_event_types.png', dpi=150, bbox_inches='tight')
print(f"\n📊 Saved: {output_dir / '1_event_types.png'}")
plt.close()

# ============================================================================
# 2. TIMELINE OF ACTIVITY
# ============================================================================
print("\n" + "="*70)
print("2️⃣  TIMELINE ANALYSIS")
print("="*70)

# Get time range
time_range = events_df['timestamp'].max() - events_df['timestamp'].min()
print(f"\n⏰ Time Range:")
print(f"   First event: {events_df['timestamp'].min()}")
print(f"   Last event:  {events_df['timestamp'].max()}")
print(f"   Duration:    {time_range}")

# Events per minute
events_df['minute'] = events_df['timestamp'].dt.floor('T')
events_per_minute = events_df.groupby('minute').size()

plt.figure(figsize=(14, 6))
plt.plot(events_per_minute.index, events_per_minute.values, linewidth=2, color='darkblue')
plt.title('System Activity Over Time (Events per Minute)', fontsize=16, fontweight='bold')
plt.xlabel('Time', fontsize=12)
plt.ylabel('Number of Events', fontsize=12)
plt.xticks(rotation=45)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / '2_timeline.png', dpi=150, bbox_inches='tight')
print(f"\n📊 Saved: {output_dir / '2_timeline.png'}")
plt.close()

# ============================================================================
# 3. TOP ACTIVE PROCESSES
# ============================================================================
print("\n" + "="*70)
print("3️⃣  MOST ACTIVE PROCESSES")
print("="*70)

top_subjects = events_df['subject'].value_counts().head(10)
print(f"\nTop 10 most active processes (by number of events):")

for i, (subject_uuid, count) in enumerate(top_subjects.items(), 1):
    # Try to find process info
    subject_info = subjects_df[subjects_df['uuid'] == subject_uuid]
    if not subject_info.empty:
        cid = subject_info.iloc[0]['cid']
        stype = subject_info.iloc[0]['type']
        print(f"   {i:2d}. PID {cid} ({stype}): {count:,} events")
    else:
        print(f"   {i:2d}. {subject_uuid[:20]}...: {count:,} events")

plt.figure(figsize=(12, 6))
top_subjects.plot(kind='barh', color='coral')
plt.title('Top 10 Most Active Processes', fontsize=16, fontweight='bold')
plt.xlabel('Number of Events', fontsize=12)
plt.ylabel('Process UUID', fontsize=12)
plt.tight_layout()
plt.savefig(output_dir / '3_active_processes.png', dpi=150, bbox_inches='tight')
print(f"\n📊 Saved: {output_dir / '3_active_processes.png'}")
plt.close()

# ============================================================================
# 4. EVENT TYPES OVER TIME
# ============================================================================
print("\n" + "="*70)
print("4️⃣  EVENT PATTERNS OVER TIME")
print("="*70)

# Top event types over time
top_event_types = events_df['type'].value_counts().head(5).index
events_subset = events_df[events_df['type'].isin(top_event_types)].copy()
events_subset['minute'] = events_subset['timestamp'].dt.floor('T')

plt.figure(figsize=(14, 6))
for event_type in top_event_types:
    subset = events_subset[events_subset['type'] == event_type]
    counts = subset.groupby('minute').size()
    plt.plot(counts.index, counts.values, label=event_type, linewidth=2, alpha=0.7)

plt.title('Top Event Types Over Time', fontsize=16, fontweight='bold')
plt.xlabel('Time', fontsize=12)
plt.ylabel('Events per Minute', fontsize=12)
plt.legend(loc='best', fontsize=10)
plt.xticks(rotation=45)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / '4_event_patterns.png', dpi=150, bbox_inches='tight')
print(f"\n📊 Saved: {output_dir / '4_event_patterns.png'}")
plt.close()

# ============================================================================
# 5. NETWORK ACTIVITY
# ============================================================================
print("\n" + "="*70)
print("5️⃣  NETWORK ACTIVITY")
print("="*70)

if len(network_df) > 0:
    print(f"\n🌐 Network Connections: {len(network_df)}")
    
    # Unique addresses
    unique_local = network_df['local_address'].nunique()
    unique_remote = network_df['remote_address'].nunique()
    print(f"   Unique local addresses:  {unique_local}")
    print(f"   Unique remote addresses: {unique_remote}")
    
    # Top remote addresses
    print(f"\n📡 Top 10 Remote Addresses:")
    top_remotes = network_df['remote_address'].value_counts().head(10)
    for i, (addr, count) in enumerate(top_remotes.items(), 1):
        print(f"   {i:2d}. {addr:40s}: {count} connections")
    
    # Ports
    print(f"\n🔌 Top Remote Ports:")
    top_ports = network_df['remote_port'].value_counts().head(10)
    for i, (port, count) in enumerate(top_ports.items(), 1):
        print(f"   {i:2d}. Port {port:6}: {count} connections")
else:
    print("\n⚠️  No network data in this sample")

# ============================================================================
# 6. DATA SUMMARY
# ============================================================================
print("\n" + "="*70)
print("📋 SUMMARY STATISTICS")
print("="*70)

summary = {
    'Total Events': len(events_df),
    'Unique Event Types': events_df['type'].nunique(),
    'Total Processes': len(subjects_df),
    'Unique Subjects in Events': events_df['subject'].nunique(),
    'Unique Objects': events_df['predicate_object'].nunique(),
    'Network Connections': len(network_df),
    'Time Span': str(time_range),
}

print()
for key, value in summary.items():
    print(f"   {key:30s}: {value}")

# Save summary to file
summary_file = output_dir / 'summary.txt'
with open(summary_file, 'w') as f:
    f.write("SENTINEL Data Summary\n")
    f.write("="*50 + "\n\n")
    for key, value in summary.items():
        f.write(f"{key:30s}: {value}\n")
    f.write("\n" + "="*50 + "\n")
    f.write(f"\nGenerated: {datetime.now()}\n")

print(f"\n💾 Summary saved to: {summary_file}")

# ============================================================================
# DONE!
# ============================================================================
print("\n" + "="*70)
print("✅ EXPLORATION COMPLETE!")
print("="*70)

print(f"\n📁 All visualizations saved to: {output_dir}")
print(f"\n📊 Files created:")
print(f"   1. 1_event_types.png      - Bar chart of event types")
print(f"   2. 2_timeline.png          - Activity over time")
print(f"   3. 3_active_processes.png  - Most active processes")
print(f"   4. 4_event_patterns.png    - Event patterns over time")
print(f"   5. summary.txt             - Text summary")

print("\n💡 Next Steps:")
print("   • Look at the PNG images to understand your data")
print("   • Read the summary.txt file")
print("   • Think about what patterns look normal vs. suspicious")
print("   • Read the ground truth to see what attacks happened")
print("   • Try to find those attacks in your timeline")

print("\n🎉 Great work! Take a break, then come back to analyze the visualizations!\n")