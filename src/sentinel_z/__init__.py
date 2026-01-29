"""
SENTINEL-Z: Zero-Shot APT Detection via Semantic Causal Graph Learning

A novel approach to APT detection that:
1. Learns semantic representations of system behavior (not raw UUIDs)
2. Models normal causal flows in a self-supervised manner
3. Detects zero-shot attacks by identifying semantic anomalies
4. Generates explainable attack narratives

Key Innovation: Instead of learning "this pattern = attack", we learn
"these semantic relationships violate normal causal expectations"
"""

__version__ = "0.1.0"
__author__ = "SENTINEL Research Team"
