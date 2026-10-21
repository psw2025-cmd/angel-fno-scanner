#!/usr/bin/env python3
"""
export_complete_55_tab_catalogs.py
Exports standalone CSV and markdown catalogs for all 55 tabs
across both workstation and repo doc trees.
"""

import os
import csv
from pathlib import Path

# Import data modules
from data_tabs_00_to_10 import (
    tab01_headers, tab01_rows,
    tab02_headers, tab02_rows,
    tab03_headers, tab03_rows,
    tab04_headers, tab04_rows,
    tab05_headers, tab05_rows,
    tab06_headers, tab06_rows,
    tab07_headers, tab07_rows,
    tab08_headers, tab08_rows,
    tab09_headers, tab09_rows,
    tab10_headers, tab10_rows
)
from data_tabs_11_to_25 import (
    tab11_headers, tab11_rows,
    tab12_headers, tab12_rows,
    tab13_headers, tab13_rows,
    tab14_headers, tab14_rows,
    tab15_headers, tab15_rows,
    tab16_headers, tab16_rows,
    tab17_headers, tab17_rows,
    tab18_headers, tab18_rows,
    tab19_headers, tab19_rows,
    tab20_headers, tab20_rows,
    tab21_headers, tab21_rows,
    tab22_headers, tab22_rows,
    tab23_headers, tab23_rows,
    tab24_headers, tab24_rows,
    tab25_headers, tab25_rows
)
from data_tabs_26_to_39 import (
    tab26_headers, tab26_rows,
    tab27_headers, tab27_rows,
    tab28_headers, tab28_rows,
    tab29_headers, tab29_rows,
    tab30_headers, tab30_rows,
    tab31_headers, tab31_rows,
    tab32_headers, tab32_rows,
    tab33_headers, tab33_rows,
    tab34_headers, tab34_rows,
    tab35_headers, tab35_rows,
    tab36_headers, tab36_rows,
    tab37_headers, tab37_rows,
    tab38_headers, tab38_rows,
    tab39_headers, tab39_rows
)
from data_tabs_m01_to_m15 import (
    tab_m01_headers, tab_m01_rows,
    tab_m02_headers, tab_m02_rows,
    tab_m03_headers, tab_m03_rows,
    tab_m04_headers, tab_m04_rows,
    tab_m05_headers, tab_m05_rows,
    tab_m06_headers, tab_m06_rows,
    tab_m07_headers, tab_m07_rows,
    tab_m08_headers, tab_m08_rows,
    tab_m09_headers, tab_m09_rows,
    tab_m10_headers, tab_m10_rows,
    tab_m11_headers, tab_m11_rows,
    tab_m12_headers, tab_m12_rows,
    tab_m13_headers, tab_m13_rows,
    tab_m14_headers, tab_m14_rows,
    tab_m15_headers, tab_m15_rows
)

TARGET_DIRS = [
    Path(r"C:\AngelFNO_Workstation\docs\reference_library"),
    Path(r"C:\AngelFNO_Workstation\repos\angel-fno-scanner\docs\reference_library")
]

ROOT_DOC_DIRS = [
    Path(r"C:\AngelFNO_Workstation\docs"),
    Path(r"C:\AngelFNO_Workstation\repos\angel-fno-scanner\docs")
]

# Ensure dirs exist
for d in TARGET_DIRS + ROOT_DOC_DIRS:
    d.mkdir(parents=True, exist_ok=True)

def write_csv(filepath, headers, rows):
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

# Catalog mappings
catalogs = [
    ("01_diagram_types.csv", tab01_headers, tab01_rows),
    ("02_trigger_phrases.csv", tab02_headers, tab02_rows),
    ("03_truth_rules.csv", tab04_headers, tab04_rows),
    ("04_cross_verification.csv", tab05_headers, tab05_rows),
    ("05_failure_resets.csv", tab06_headers, tab06_rows),
    ("08_visual_catalog.csv", tab03_headers, tab03_rows),
    ("09_project_facts.csv", tab29_headers, tab29_rows),
    ("10_glossary.csv", tab28_headers, tab28_rows),
    ("11_agent_findings.csv", tab23_headers, tab23_rows),
    ("12_global_recommendations.csv", tab24_headers, tab24_rows),
    ("13_gap_analysis.csv", tab25_headers, tab25_rows),
    ("14_sources_cited.csv", tab30_headers, tab30_rows),
    ("15_prediction_accuracy.csv", tab32_headers, tab32_rows),
    ("16_market_top_ce_pe.csv", tab33_headers, tab33_rows),
    ("17_learning_from_market.csv", tab34_headers, tab34_rows),
    ("18_self_learning_proof.csv", tab35_headers, tab35_rows),
    # 15 Missing Tabs (M01 to M15)
    ("19_node_registry.csv", tab_m01_headers, tab_m01_rows),
    ("20_edge_registry.csv", tab_m02_headers, tab_m02_rows),
    ("21_cluster_map.csv", tab_m03_headers, tab_m03_rows),
    ("22_centrality_scores.csv", tab_m04_headers, tab_m04_rows),
    ("23_force_layout.csv", tab_m05_headers, tab_m05_rows),
    ("24_trace_paths.csv", tab_m06_headers, tab_m06_rows),
    ("25_latency_matrix.csv", tab_m07_headers, tab_m07_rows),
    ("26_bottleneck_registry.csv", tab_m08_headers, tab_m08_rows),
    ("27_failure_propagation.csv", tab_m09_headers, tab_m09_rows),
    ("28_complexity_baseline.csv", tab_m10_headers, tab_m10_rows),
    ("29_complexity_target.csv", tab_m11_headers, tab_m11_rows),
    ("30_abstraction_rules.csv", tab_m12_headers, tab_m12_rows),
    ("31_live_telemetry_feed.csv", tab_m13_headers, tab_m13_rows),
    ("32_optimization_queue.csv", tab_m14_headers, tab_m14_rows),
    ("33_slo_burn_rate.csv", tab_m15_headers, tab_m15_rows)
]

print("Exporting standalone reference catalogs...")
for fname, headers, rows in catalogs:
    for tdir in TARGET_DIRS:
        write_csv(tdir / fname, headers, rows)
    # Also write core ones to root docs
    if fname in ["01_diagram_types.csv", "02_trigger_phrases.csv", "03_truth_rules.csv", "04_cross_verification.csv"]:
        short_name = fname.split("_", 1)[1]
        for rdir in ROOT_DOC_DIRS:
            write_csv(rdir / short_name, headers, rows)

# Write text files (prompts and contracts)
prompt_text = "\n\n".join([f"=== {p[0]}: {p[1]} ===\nPurpose: {p[2]}\nSystem: {p[3]}\n\n{p[4]}" for p in tab07_rows])
contract_text = "\n".join([f"Line {c[0]} [{c[1]}]: {c[2]} - {c[3]} (Verify: {c[4]})" for c in tab08_rows])

for tdir in TARGET_DIRS:
    with open(tdir / "07_agent_prompts.txt", 'w', encoding='utf-8') as f:
        f.write(prompt_text)
    with open(tdir / "17_master_contract.txt", 'w', encoding='utf-8') as f:
        f.write(contract_text)

for rdir in ROOT_DOC_DIRS:
    with open(rdir / "DIAGRAM_FIRST_PROMPT.txt", 'w', encoding='utf-8') as f:
        f.write(tab07_rows[0][4])
    with open(rdir / "MASTER_CONTRACT.txt", 'w', encoding='utf-8') as f:
        f.write(contract_text)

# Build index markdown
index_md_content = """# Master Reference Library Catalog (Version 2.0)
**Generated:** 2026-10-14  
**Authority:** PSW Autonomous Principal Engineer & SRE System  
**Specification:** w.txt & deepseek diagram.txt  
**Master Workbook:** `PSW_Angel_FNO_Reference_Library.xlsx` (55 Tabs, 1,058 Data Rows)

## Reference Files Inventory

| File | Rows | Category | Description | Maps To Image |
|---|---|---|---|---|
| `01_diagram_types.csv` | 40 | Visual Design | 40 visual diagram types with use-cases & links | Both Images |
| `02_trigger_phrases.csv` | 145 | AI Interface | 145 conversational trigger phrases to extract outputs | Image 2 |
| `03_truth_rules.csv` | 20 | Governance | 20 atomic truth-enforcement rules preventing placeholders | Image 2 |
| `04_cross_verification.csv` | 40 | Quality Assurance | 40 cross-verification patterns with command templates | Image 2 |
| `05_failure_resets.csv` | 16 | Governance | 16 one-word reset tokens and escalation procedures | Image 2 |
| `07_agent_prompts.txt` | 5 | Prompt Engineering | 5 paste-ready master system prompts and contracts | Neither |
| `08_visual_catalog.csv` | 65 | Observability | 65 monitoring views with Node_Count, Edge_Count, Render_Mode | Image 1 + 2 |
| `09_project_facts.csv` | 20 | Ground Truth | 20 verified configuration facts with commands | Neither |
| `10_glossary.csv` | 15 | Terminology | 15 engineering translations of metaphors + quantum math | Image 1 |
| `11_agent_findings.csv` | 10 | Innovation | 10 valuable autonomous agent architectural discoveries | Neither |
| `12_global_recommendations.csv` | 12 | Roadmap | 12 global SRE & cloud best practices with owners | Neither |
| `13_gap_analysis.csv` | 8 | Project Mgmt | 8 audit deltas with remediated status | Neither |
| `14_sources_cited.csv` | 10 | Bibliography | 10 official documentation citations and industry books | Neither |
| `15_prediction_accuracy.csv` | 15 | Machine Learning | 15 prediction records with Brier scores and CIs | Image 1 |
| `16_market_top_ce_pe.csv` | 12 | Quantitative | 12 actual market winner options with miss analysis | Neither |
| `17_learning_from_market.csv` | 8 | Machine Learning | 8 Bayesian factor weight adjustments with deltas | Image 1 |
| `18_self_learning_proof.csv` | 8 | Governance | 8 self-learning mechanisms with raw terminal outputs | Image 2 |
| `19_node_registry.csv` | 25 | Graph Primitives | 25 nodes (services, tables, sheets, secrets, daemons) | Image 1 + 2 |
| `20_edge_registry.csv` | 35 | Graph Primitives | 35 edges (protocols, RPM, latency, error rates) | Image 1 + 2 |
| `21_cluster_map.csv` | 8 | Graph Topology | 8 colored regional domain clusters | Image 1 |
| `22_centrality_scores.csv` | 25 | Network Science | Betweenness, closeness, eigenvector, degree rankings | Image 1 |
| `23_force_layout.csv` | 25 | Physics Sim | Pre-computed X/Y coordinates for D3/NetworkX physics | Image 1 |
| `24_trace_paths.csv` | 16 | Observability | Hop-by-hop distributed trace spans for Control Room P2 | Image 2 |
| `25_latency_matrix.csv` | 15 | Performance | Inter-service latency matrix (P50, P90, P99) | Image 2 |
| `26_bottleneck_registry.csv` | 8 | Performance | System bottlenecks, symptoms, and mitigations | Image 2 |
| `27_failure_propagation.csv` | 8 | SRE Resiliency | Failure cascade scenarios and fail-closed mechanisms | Image 2 |
| `28_complexity_baseline.csv` | 10 | Architecture | Baseline architectural complexity (219 nodes, 3066 edges) | Image 2 |
| `29_complexity_target.csv` | 10 | Architecture | Target simplified state metrics & reduction factors | Image 2 |
| `30_abstraction_rules.csv` | 8 | Architecture | Domain boundary protocols & encapsulation rules | Image 2 |
| `31_live_telemetry_feed.csv` | 15 | Live Telemetry | Real-time telemetry metrics, values & thresholds | Image 2 |
| `32_optimization_queue.csv` | 10 | Continuous SRE | Backlog of continuous improvements ranked by ROI | Image 2 |
| `33_slo_burn_rate.csv` | 8 | SRE Reliability | Service level objectives, error budgets & burn rates | Image 2 |
"""

for tdir in TARGET_DIRS:
    with open(tdir / "18_index.md", 'w', encoding='utf-8') as f:
        f.write(index_md_content)

print("All standalone reference catalogs, prompts, and index files successfully exported.")
