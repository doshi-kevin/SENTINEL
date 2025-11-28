"""
Find Interesting Patterns - What to Investigate Next
Highlights suspicious or unusual patterns in your data
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

output_dir = Path('data/processed/analysis/')
output_dir.mkdir(parents=True, exist_ok=True)

print("="*70)
print("🔍 Pattern Detection - Finding Interesting Events")
print("="*70)

# Load data
print("\n📥 Loading data...")
events_df = pd.read_csv('data/processed/events.csv')
subjects_df = pd.read_csv('data/processed/subjects.csv')
network_df = pd.read_csv('data/processed/network.csv')

events_df['timestamp'] = pd.to_datetime(events_df['timestamp'])

print(f"✅ Loaded {len(events_df):,} events")

# ============================================================================
# 1. BURST DETECTION - Sudden spikes in activity
# ============================================================================
print("\n" + "="*70)
print("1️⃣  ACTIVITY BURSTS (Potential Attack Windows)")
print("="*70)

events_df['minute'] = events_df['timestamp'].dt.floor('T')
events_per_minute = events_df.groupby('minute').size()

# Find bursts (more than 2x the average)
avg_events = events_per_minute.mean()
threshold = avg_events * 2

bursts = events_per_minute[events_per_minute > threshold].sort_values(ascending=False)

print(f"\n📊 Average events per minute: {avg_events:.1f}")
print(f"🚨 Burst threshold (2x avg): {threshold:.1f}")
print(f"\n⚡ Found {len(bursts)} time windows with unusual activity:\n")

for i, (timestamp, count) in enumerate(bursts.head(10).items(), 1):
    print(f"   {i:2d}. {timestamp} - {count:,} events ({count/avg_events:.1f}x normal)")

# ============================================================================
# 2. RARE EVENT TYPES - Unusual events worth investigating
# ============================================================================
print("\n" + "="*70)
print("2️⃣  RARE EVENTS (Potentially Suspicious)")
print("="*70)

event_counts = events_df['type'].value_counts()
rare_events = event_counts[event_counts < 10]  # Less than 10 occurrences

print(f"\n🔍 Found {len(rare_events)} rare event types:\n")
for event_type, count in rare_events.items():
    # Find when they occurred
    timestamps = events_df[events_df['type'] == event_type]['timestamp']
    first_occurrence = timestamps.min()
    print(f"   • {event_type:40s}: {count:2d} times (first at {first_occurrence})")

# ============================================================================
# 3. PROCESS CHAINS - Parent-child relationships
# ============================================================================
print("\n" + "="*70)
print("3️⃣  PROCESS RELATIONSHIPS")
print("="*70)

# Count processes with parents
processes_with_parents = subjects_df[subjects_df['parent_subject'].notna()]
print(f"\n👨‍👦 Processes with parent relationships: {len(processes_with_parents)}")
print(f"🔗 Total processes: {len(subjects_df)}")

# Find processes that spawned children
parent_counts = subjects_df[subjects_df['parent_subject'].notna()]['parent_subject'].value_counts()

print(f"\n👪 Top processes that spawned children:\n")
for i, (parent_uuid, child_count) in enumerate(parent_counts.head(5).items(), 1):
    parent_info = subjects_df[subjects_df['uuid'] == parent_uuid]
    if not parent_info.empty:
        cid = parent_info.iloc[0]['cid']
        print(f"   {i}. PID {cid}: spawned {child_count} child processes")

# ============================================================================
# 4. NETWORK PATTERNS
# ============================================================================
print("\n" + "="*70)
print("4️⃣  NETWORK PATTERNS")
print("="*70)

if len(network_df) > 0:
    # Find repeated connections to same address
    remote_counts = network_df['remote_address'].value_counts()
    repeated = remote_counts[remote_counts > 1]
    
    print(f"\n🌐 Repeated connections to same remote address:\n")
    for addr, count in repeated.head(10).items():
        print(f"   • {addr:40s}: {count} connections")
    
    # Unusual ports
    common_ports = [80, 443, 53, 22, 21, 25, 110, 143, 3389]
    unusual_ports = network_df[~network_df['remote_port'].isin(common_ports)]
    
    if len(unusual_ports) > 0:
        print(f"\n🔌 Unusual ports (not common services):")
        port_counts = unusual_ports['remote_port'].value_counts().head(10)
        for port, count in port_counts.items():
            print(f"   • Port {port}: {count} connections")
else:
    print("\n⚠️  No network data available")

# ============================================================================
# 5. TIME GAPS - Periods of no activity (suspicious?)
# ============================================================================
print("\n" + "="*70)
print("5️⃣  TIME GAPS (Periods of No Activity)")
print("="*70)

events_sorted = events_df.sort_values('timestamp')
time_diffs = events_sorted['timestamp'].diff()

# Gaps longer than 1 minute
long_gaps = time_diffs[time_diffs > timedelta(minutes=1)].sort_values(ascending=False)

print(f"\n⏸️  Found {len(long_gaps)} gaps longer than 1 minute:\n")
for i, (idx, gap) in enumerate(long_gaps.head(5).items(), 1):
    end_time = events_sorted.loc[idx, 'timestamp']
    start_time = end_time - gap
    print(f"   {i}. {start_time} to {end_time}")
    print(f"      Gap: {gap}")

# ============================================================================
# 6. INVESTIGATION TARGETS
# ============================================================================
print("\n" + "="*70)
print("🎯 RECOMMENDED INVESTIGATION TARGETS")
print("="*70)

targets = []

# Target 1: Biggest burst
if len(bursts) > 0:
    biggest_burst = bursts.index[0]
    targets.append(f"Time window with most activity: {biggest_burst}")

# Target 2: Rare events
if len(rare_events) > 0:
    first_rare = rare_events.index[0]
    targets.append(f"Investigate rare event type: {first_rare}")

# Target 3: Most active process
most_active_subject = events_df['subject'].value_counts().index[0]
subject_info = subjects_df[subjects_df['uuid'] == most_active_subject]
if not subject_info.empty:
    cid = subject_info.iloc[0]['cid']
    targets.append(f"Most active process: PID {cid}")

print("\n📋 Start your investigation here:\n")
for i, target in enumerate(targets, 1):
    print(f"   {i}. {target}")

# ============================================================================
# 7. SAVE FINDINGS TO FILE
# ============================================================================
findings_file = output_dir / 'interesting_patterns.txt'
with open(findings_file, 'w') as f:
    f.write("SENTINEL - Interesting Patterns Report\n")
    f.write("="*70 + "\n\n")
    
    f.write("ACTIVITY BURSTS\n")
    f.write("-"*70 + "\n")
    for timestamp, count in bursts.head(5).items():
        f.write(f"{timestamp} - {count:,} events\n")
    
    f.write("\n\nRARE EVENTS\n")
    f.write("-"*70 + "\n")
    for event_type, count in rare_events.items():
        f.write(f"{event_type}: {count} occurrences\n")
    
    f.write("\n\nRECOMMENDED INVESTIGATIONS\n")
    f.write("-"*70 + "\n")
    for i, target in enumerate(targets, 1):
        f.write(f"{i}. {target}\n")
    
    f.write(f"\n\nGenerated: {datetime.now()}\n")

print(f"\n💾 Findings saved to: {findings_file}")

print("\n" + "="*70)
print("✅ PATTERN ANALYSIS COMPLETE!")
print("="*70)

print("\n💡 What to do next:")
print("   1. Look at the activity bursts - these might be attacks")
print("   2. Investigate rare events - unusual behavior often = malicious")
print("   3. Check the most active processes - are they normal?")
print("   4. Compare these times to the ground truth report")
print("   5. Manually examine events during burst windows")

print("\n📖 Read: data/processed/analysis/interesting_patterns.txt")
print("\n🎉 You're ready to find attacks! Take a break and come back fresh!\n")