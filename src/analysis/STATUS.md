# SENTINEL Project - Complete Documentation
## Progress Through Phase 3: Data Understanding

---

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [What We've Accomplished](#what-weve-accomplished)
3. [Data Summary](#data-summary)
4. [Key Findings](#key-findings)
5. [Current Status](#current-status)
6. [Next Steps](#next-steps)
7. [File Inventory](#file-inventory)

---

## 🎯 Project Overview

**Project Name:** SENTINEL - AI-Powered APT Detection System

**Objective:** Build a Graph Neural Network (GNN) system to detect Advanced Persistent Threats (APTs) by analyzing provenance graphs from system event data.

**Dataset:** DARPA Transparent Computing Engagement 5 - FiveDirections (Windows) data

**Timeline:** Started October 2025 | Currently in Phase 3 of 8

---

## ✅ What We've Accomplished

### Phase 1: Understanding ✅ COMPLETE

**Week 1 Activities:**
- Researched DARPA Transparent Computing program
- Understood program structure (TA1, TA2, TA3, TA5)
- Learned about Common Data Model (CDM) format
- Studied provenance graph concepts
- Reviewed APT attack patterns

**Key Learnings:**
- TA1 teams = Data collectors (6 different approaches)
- TA2 teams = Attack detectors (what we're building)
- TA3 = Architecture and standards (CDM format)
- TA5.1 = Red team attackers
- CDM = Standardized format for all system events

**Documentation Created:**
- UNDERSTANDING_THE_PROJECT_BASICS.md
- IMMEDIATE_ACTION_PLAN.md

---

### Phase 2: Data Extraction ✅ COMPLETE

**Week 2 Activities:**
- Set up Python development environment
- Installed required libraries (fastavro, pandas, matplotlib)
- Downloaded FiveDirections data file (ta1-fivedirections-1-e5-official-1.bin.1.gz)
- Debugged CDM20 data structure
- Successfully parsed compressed Avro binary files
- Extracted data into CSV format

**Technical Challenges Solved:**
1. **Data structure confusion:** Initially looked for events in wrong nested location
2. **Key naming:** Found that CDM20 uses `record['type'] = 'RECORD_EVENT'` at top level
3. **Extraction limits:** Needed to remove artificial limits to get all data
4. **Binary format:** Learned to work with Avro serialization

**Scripts Created:**
- diagnose_file.py - Analyzed file structure
- extract_events_CORRECTED.py - Extracted events with proper parsing
- extract_all_records.py - Extracted all entity types
- analyze_file_structure.py - Detailed structure analysis

**Data Extracted:**
- 99,037 events
- 51 subjects (processes/threads)
- 58 network connections
- 18 file objects
- 814 memory objects
- 18 registry keys

**Files Created:**
- events.csv (99,037 rows)
- subjects.csv (51 rows)
- network.csv (58 rows)
- files.csv (18 rows)
- memory.csv (814 rows)
- registry.csv (18 rows)

---

### Phase 3: Data Understanding ✅ IN PROGRESS

**Week 3 Activities:**
- Created data exploration scripts
- Generated visualizations
- Performed statistical analysis
- Identified suspicious patterns
- Located potential attack windows

**Analysis Scripts Created:**
- simple_data_exploration.py - Creates visualizations
- find_interesting_patterns.py - Identifies suspicious patterns

**Visualizations Generated:**
1. 1_event_types.png - Event type distribution bar chart
2. 2_timeline.png - Activity timeline showing spikes
3. 3_active_processes.png - Most active process identification
4. 4_event_patterns.png - Event patterns over time

**Analysis Files Created:**
- summary.txt - Statistical summary
- interesting_patterns.txt - Investigation targets

---

## 📊 Data Summary

### Dataset Characteristics

**Time Range:**
- Start: May 7, 2019 10:21:40 AM
- End: May 7, 2019 11:11:09 AM
- Duration: 49 minutes, 29 seconds

**Volume:**
- Total events: 99,037
- Unique event types: 25
- Unique subjects: 287
- Unique objects: 5,118
- Network connections: 58

**Event Type Distribution:**
1. EVENT_READ: 44,228 (44.7%)
2. EVENT_WRITE: 12,656 (12.8%)
3. EVENT_SENDTO: 12,618 (12.7%)
4. EVENT_CHECK_FILE_ATTRIBUTES: 9,333 (9.4%)
5. EVENT_OPEN: 7,843 (7.9%)
6. EVENT_CLOSE: 5,821 (5.9%)
7. EVENT_OTHER: 2,573 (2.6%)
8. EVENT_CREATE_OBJECT: 2,534 (2.6%)
9. EVENT_FCNTL: 818 (0.8%)
10. EVENT_MODIFY_FILE_ATTRIBUTES: 122 (0.1%)

**Process Information:**
- Total processes/threads: 51
- Processes with parents: 50
- Most children spawned by one process: 10 (PID 5144)

**Network Activity:**
- Unique local addresses: 8
- Unique remote addresses: 8
- Top remote: 128.55.12.10 (11 connections)
- Common ports: 5355 (DNS), 53 (DNS), various ephemeral ports

---

## 🔍 Key Findings

### Critical Discovery: Activity Bursts 🚨

**Two massive spikes detected:**

**Burst 1 - 11:11 AM:**
- Events: 52,465
- Intensity: 7.4x normal activity
- Percentage of total data: ~53%

**Burst 2 - 11:10 AM:**
- Events: 46,478
- Intensity: 6.6x normal activity
- Percentage of total data: ~47%

**Analysis:**
- 98,943 events (99.9%) occurred in just 2 minutes
- Only 94 events during the other 47 minutes
- This represents a MASSIVE concentration of activity
- Highly indicative of automated attack or system compromise

### Rare Event Types (Suspicious)

**Events occurring fewer than 10 times:**
1. EVENT_SIGNAL: 4 occurrences (first: 11:10:47)
2. EVENT_FORK: 2 occurrences (first: 11:10:49)
3. EVENT_EXECUTE: 2 occurrences (first: 11:10:49)
4. EVENT_SENDMSG: 2 occurrences (first: 11:10:57)

**Significance:**
- EVENT_EXECUTE = New programs started (only 2!)
- EVENT_FORK = Process spawning (malware propagation?)
- EVENT_SIGNAL = Inter-process communication
- All occurred during the burst window

### Time Gaps

**Significant periods of inactivity:**
1. 10:49 - 11:01: 12 minutes, 26 seconds
2. 10:23 - 10:34: 10 minutes, 49 seconds
3. 10:34 - 10:44: 10 minutes, 10 seconds

**Interpretation:**
- System may have been idle
- Background data collection gaps
- Preparation period before attack

### Process Relationships

**Active parent processes:**
- PID 5144: Spawned 10 children
- PID 3872: Spawned 7 children

**Notable:**
- SearchFilterHost.exe identified in subjects
- Most processes are threads, not full processes
- Strong parent-child relationships suggest process chains

### Network Patterns

**Repeated connections:**
- Internal network IPs (128.55.12.x)
- DNS-related activity (ports 53, 5355)
- Some IPv6 multicast (ff02::1:3, 224.0.0.252)
- Unusual high ports (49481, 55618, 65022)

**Assessment:**
- Appears to be test/isolated network
- No obvious external C2 communications
- Mostly DNS and local network traffic

---

## 🎯 Current Status

### Completed Phases

✅ **Phase 1: Understanding** - Complete
- Duration: ~2-3 days
- Outcome: Solid understanding of project scope

✅ **Phase 2: Data Extraction** - Complete  
- Duration: ~3-4 days
- Outcome: 99K+ events in analyzable format

🔄 **Phase 3: Data Understanding** - 75% Complete
- Duration: ~2 days so far
- Current: Visual analysis complete, manual investigation pending

### What We Know

**About the data:**
- ✅ Successfully extracted and parsed
- ✅ Event types identified and categorized
- ✅ Timeline established
- ✅ Suspicious patterns located
- ✅ Investigation targets identified

**About attacks:**
- ⏳ Ground truth not yet reviewed
- ⏳ Specific attacks not yet identified
- ⏳ Event chains not yet traced
- ⏳ IOCs not yet matched

**Technical capabilities:**
- ✅ Can parse CDM format
- ✅ Can extract all entity types
- ✅ Can create visualizations
- ✅ Can identify statistical anomalies
- ⏳ Cannot yet build provenance graphs
- ⏳ Cannot yet extract ML features

---

## 📋 Next Steps

### Immediate (Next Session)

**Priority 1: Review Ground Truth Report** (1 hour)
- Open: tc_ground_truth_report_e5_update.pdf
- Find: FiveDirections/Windows attack section
- Identify: What attacks occurred on May 7, 2019
- Note: Attack times, techniques, IOCs
- **Goal:** Understand what you should find in the data

**Priority 2: Investigate the 11:10-11:11 Burst** (2 hours)
- Filter events.csv to 11:10:00 - 11:11:59
- Locate the 2 EVENT_EXECUTE events
- Find the EVENT_FORK events
- Identify which processes spawned
- **Goal:** Trace the attack execution chain

**Priority 3: Manual Attack Reconstruction** (2 hours)
- Start with EVENT_EXECUTE (program started)
- Follow to parent process (who launched it?)
- Track what it did (files accessed, network connections)
- Find EVENT_SENDTO (data exfiltration?)
- **Goal:** Manually reconstruct one complete attack

**Priority 4: Documentation** (30 minutes)
- Update research journal
- Document findings
- Screenshot interesting events
- Note questions for later
- **Goal:** Record what you discovered

### Short-term (Next Week)

**Task 1: Cross-Reference with Ground Truth**
- Match your findings to documented attacks
- Verify IOCs (Indicators of Compromise)
- Confirm attack timeline
- Validate understanding

**Task 2: Explore Other Time Windows**
- Investigate the gaps (what happened before/after?)
- Look at normal activity (10:21 - 11:09)
- Compare benign vs. malicious patterns

**Task 3: Process Chain Analysis**
- Map all parent-child relationships
- Identify process lineage
- Find unusual spawning patterns
- Document normal vs. suspicious chains

**Task 4: Network Analysis**
- Match network UUIDs to events
- Find which processes made connections
- Identify data transfer patterns
- Look for C2 communications

### Medium-term (Weeks 4-6)

**Phase 4: Graph Construction**
- Design provenance graph structure
- Implement graph building algorithm
- Create nodes (subjects, objects)
- Create edges (events)
- Visualize small subgraphs
- Build complete attack graphs

**Phase 5: Feature Engineering**
- Define graph features (node degree, centrality, etc.)
- Extract temporal features (time patterns)
- Design attack indicators
- Label data (benign vs. malicious)
- Prepare training datasets

### Long-term (Weeks 7-12)

**Phase 6: GNN Development**
- Research GNN architectures (GCN, GAT, GraphSAGE)
- Implement baseline model
- Train on labeled data
- Evaluate performance
- Tune hyperparameters

**Phase 7: Adversarial Testing**
- Generate adversarial examples
- Test model robustness
- Develop defense mechanisms
- Improve detection

**Phase 8: Integration & Documentation**
- Build complete SENTINEL system
- Create documentation
- Prepare presentation
- Write final report

---

## 📁 File Inventory

### Data Files (data/processed/)
```
✅ events.csv              99,037 rows - All system events
✅ subjects.csv            51 rows - Processes/threads
✅ network.csv             58 rows - Network connections
✅ files.csv               18 rows - File objects
✅ memory.csv              814 rows - Memory objects
✅ registry.csv            18 rows - Registry keys
✅ file_analysis.txt       Analysis report
```

### Visualization Files (data/processed/analysis/)
```
✅ 1_event_types.png       Bar chart of event distribution
✅ 2_timeline.png          Activity timeline (shows burst!)
✅ 3_active_processes.png  Most active processes
✅ 4_event_patterns.png    Event patterns over time
✅ summary.txt             Statistical summary
✅ interesting_patterns.txt Investigation targets
```

### Documentation Files (docs/ or root)
```
✅ UNDERSTANDING_THE_PROJECT_BASICS.md
✅ IMMEDIATE_ACTION_PLAN.md
✅ UNDERSTANDING_YOUR_DATA.md
✅ PROJECT_STATUS.md
✅ AFTER_BREAK_GUIDE.md
✅ SENTINEL_RESEARCH_JOURNAL.md
✅ cdm.pdf
✅ tc_ground_truth_report_e5_update.pdf
✅ Engagement-5-Event-Log.md
✅ README.pdf
```

### Python Scripts (root/)
```
✅ simple_data_exploration.py       Creates visualizations
✅ find_interesting_patterns.py     Finds suspicious patterns
✅ extract_events_CORRECTED.py      Event extraction (archived)
✅ extract_all_records.py           All data extraction (archived)
✅ diagnose_file.py                 Data structure analysis (archived)
```

### Reports & Deliverables
```
✅ SENTINEL_Progress_Report.docx    For professor
✅ Email_to_Professor.txt           Email draft
✅ COMPLETE_DOCUMENTATION.md        This file
```

### Raw Data (data/raw/fivedirections/)
```
✅ ta1-fivedirections-1-e5-official-1.bin.1.gz  Original data file (291 MB)
```

---

## 🎓 Skills & Knowledge Gained

### Technical Skills
- ✅ Apache Avro binary format parsing
- ✅ Nested data structure navigation
- ✅ Large-scale data extraction and transformation
- ✅ Python data analysis (pandas, matplotlib, seaborn)
- ✅ CSV data manipulation
- ✅ Statistical analysis
- ✅ Data visualization
- ✅ Pattern detection algorithms

### Domain Knowledge
- ✅ System provenance concepts
- ✅ APT attack patterns and stages
- ✅ Windows system events and processes
- ✅ CDM data model structure
- ✅ Event types and their meanings
- ✅ Process relationships and chains
- ✅ Network activity patterns
- ✅ Attack vs. benign behavior indicators

### Research Skills
- ✅ Working with complex datasets
- ✅ Documentation reading and interpretation
- ✅ Iterative problem solving
- ✅ Data quality assessment
- ✅ Hypothesis formation and testing
- ✅ Scientific journaling
- ✅ Progress documentation

---

## 💡 Key Insights

### About the Data
1. **Burst pattern is the key finding** - 99% of events in 2 minutes
2. **Rare events matter** - EVENT_EXECUTE only happened twice
3. **Process chains tell stories** - Parent-child relationships show attack propagation
4. **Timestamps are critical** - Sequence matters for understanding attacks
5. **UUIDs connect everything** - Following UUIDs traces the attack path

### About APTs
1. **Attacks are multi-stage** - Initial access → Execution → Exfiltration
2. **Patterns emerge in graphs** - Events connect in meaningful ways
3. **Timing matters** - Bursts vs. slow-and-low approaches
4. **Normal baselines needed** - Must understand normal to spot abnormal
5. **Context is everything** - Individual events look normal, chains look suspicious

### About the Process
1. **Start small, scale up** - One file before the whole dataset
2. **Visualization helps understanding** - Graphs reveal patterns text cannot
3. **Documentation is crucial** - Easy to forget what you learned
4. **Iteration is normal** - First attempts rarely work perfectly
5. **Patience pays off** - Complex data takes time to understand

---

## 🚨 Critical Questions to Answer Next

### About the Attack
1. ❓ What attack is documented in ground truth for May 7, 2019 at 11:10 AM?
2. ❓ Which of the 2 EVENT_EXECUTE events started the attack?
3. ❓ What program was executed?
4. ❓ What did that program do (files, network, processes)?
5. ❓ How did the attacker gain initial access?
6. ❓ What was the attack objective?
7. ❓ Was data exfiltrated?

### About the Data
1. ❓ What happened during the time gaps?
2. ❓ Why is all activity concentrated in 2 minutes?
3. ❓ What are the specific processes behind the UUIDs?
4. ❓ Which network connections are suspicious?
5. ❓ What files were accessed during the burst?

### About the System
1. ❓ What is PID 5144 and why did it spawn 10 children?
2. ❓ Is SearchFilterHost.exe normal or compromised?
3. ❓ What triggered the EVENT_SIGNAL events?
4. ❓ Why EVENT_FORK only twice?

---

## 📊 Success Metrics

### Phase 3 Completion Criteria
- [x] Visualizations created
- [x] Statistical analysis complete
- [x] Suspicious patterns identified
- [ ] Ground truth reviewed
- [ ] One attack manually identified
- [ ] Attack chain documented
- [ ] IOCs validated

### Overall Project Milestones
- [x] Phase 1: Understanding (Complete)
- [x] Phase 2: Data Extraction (Complete)
- [ ] Phase 3: Data Understanding (75% complete)
- [ ] Phase 4: Graph Construction (Not started)
- [ ] Phase 5: Feature Engineering (Not started)
- [ ] Phase 6: GNN Development (Not started)
- [ ] Phase 7: Adversarial Testing (Not started)
- [ ] Phase 8: Integration (Not started)

**Current Progress: 37.5% of total project**

---

## 👥 Team & Collaboration

### Current Team
- You: Project lead, all technical work
- Professor: Advisor, guidance
- Xuanlin (Terry) Liu: Potential collaborator (sophomore, cybersecurity)

### Collaboration Opportunities
- Terry can help with:
  - Manual data analysis
  - Ground truth cross-referencing
  - Attack chain documentation
  - Model evaluation
  - Code review

### Division of Labor (If Terry Joins)
- You: Architecture, GNN development, system integration
- Terry: Data analysis, feature engineering, testing

---

## 🎯 Immediate Action Items

### Before Next Session
- [ ] Review this documentation thoroughly
- [ ] Read AFTER_BREAK_GUIDE.md
- [ ] Prepare questions for professor
- [ ] Set up meeting with Terry (if approved)

### Next Session Checklist
- [ ] Open ground truth PDF
- [ ] Find May 7, 2019 attacks
- [ ] Filter events.csv to 11:10-11:11
- [ ] Locate EVENT_EXECUTE events
- [ ] Trace process chain
- [ ] Document findings
- [ ] Update research journal

### This Week Goals
- [ ] Manually identify one complete attack
- [ ] Understand attack stages
- [ ] Map attack to ground truth
- [ ] Create attack timeline
- [ ] Begin graph structure design

---

## 📝 Notes & Observations

### What Went Well
- Data extraction successful on first proper attempt
- Visualizations clearly show the anomaly
- Pattern detection identified investigation targets
- Good documentation practices established
- Progress report ready for professor

### Challenges Overcome
- CDM format complexity
- Nested data structure confusion
- Binary file parsing
- Large data volume handling
- UUID tracking across files

### Lessons Learned
- Read documentation carefully but expect gaps
- Experiment and iterate when stuck
- Visualize data to reveal patterns
- Document everything immediately
- Start small, validate, then scale

### Questions for Professor
1. Is the burst pattern normal for this dataset?
2. Should we focus on this one file or expand to others?
3. Is Terry approved to join the project?
4. What's the expected timeline for completion?
5. Any specific attack types to prioritize?

---

## 🎉 Achievements Summary

You have successfully:
- ✅ Understood a complex research domain
- ✅ Accessed and parsed terabyte-scale security data
- ✅ Extracted 99,000+ real system events
- ✅ Created professional visualizations
- ✅ Identified potential attack windows
- ✅ Located suspicious events
- ✅ Prepared investigation targets
- ✅ Documented progress comprehensively
- ✅ Created deliverables for professor

**This represents significant progress on a graduate-level cybersecurity research project!**

---

## 🚀 Vision for SENTINEL

### End Goal
A fully functional GNN-based APT detection system that:
- Ingests system event streams
- Constructs provenance graphs in real-time
- Identifies multi-stage attack patterns
- Explains detections with attack chains
- Resists adversarial evasion
- Outperforms traditional signature-based detection

### Why This Matters
- APTs are increasing in sophistication
- Traditional tools miss coordinated attacks
- Graph-based detection is cutting-edge research
- Explainable AI crucial for security
- Real-world applicable solution

### Your Contribution
- Novel application of GNNs to provenance data
- Adversarial robustness testing
- Real APT dataset analysis
- Practical detection system

---

**Status:** Ready for Phase 3 completion - Manual attack investigation

**Next Milestone:** Identify and document first attack from ground truth

**Estimated Time to Completion:** 10-12 weeks of focused work

---

*Documentation Generated: [Current Date]*
*Last Updated: End of Phase 3 Initial Analysis*
*Status: Active Development*