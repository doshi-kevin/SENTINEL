/**
 * Sentinel-Z API client.
 *
 * Wraps the FastAPI backend (src/sentinel_z/api/server.py) with typed
 * fetch helpers. Configured via NEXT_PUBLIC_API_URL environment variable.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ModelCard {
  roc_auc_test: number;
  precision_test: number;
  recall_test: number;
  f1_test: number;
  fpr_test: number;
  threshold: number;
  feature_importances: Record<string, number>;
  n_train: number;
  n_val: number;
  n_test: number;
  n_attacks_test: number;
  trained_on: string;
  limitations: string[];
  model_version: string;
}

export interface AttackNarrative {
  window_id: number;
  stage: string;
  summary: string;
  risk_factors: string[];
  high_risk_entities: string[];
  mitre_hints: string[];
  raw_score: number;
  confidence: "low" | "medium" | "high";
  signals?: Record<string, number>;
}

export interface CampaignStory {
  progression_id: string;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  title: string;
  narrative: string;
  chapters: AttackNarrative[];
  mitre_tactics: string[];
}

export interface DetectionResult {
  window_id: number;
  anomaly_score: number;
  is_anomaly: boolean;
  threshold: number;
  top_features: Record<string, number>;
}

export interface GraphNode {
  id: string;
  node_type: "subject" | "object";
  [k: string]: unknown;
}

export interface GraphEdge {
  source: number;
  target: number;
  event: string;
  ts: string;
}

export interface ProvenanceGraph {
  nodes: GraphNode[];
  links: GraphEdge[];
  directed?: boolean;
}

async function get<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${url} failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  status: () => get<{ status: string; message: string }>("/status"),

  modelCard: () => get<ModelCard>("/api/v1/model_card"),

  detections: () => get<DetectionResult[]>("/api/v1/detections"),

  campaigns: () => get<CampaignStory[]>("/api/v1/campaigns"),

  windowStory: (windowId: number) =>
    get<AttackNarrative>(`/sentinel-z/story/window/${windowId}`),

  windowGraph: (windowId: number) =>
    get<ProvenanceGraph>(`/graph/${windowId}?window=0`),

  timeline: () =>
    get<{
      time_series: Array<{
        window_id: number;
        time: string;
        nodes: number;
        edges: number;
        label: number;
        anomaly_score: number;
        attack_stage: string;
      }>;
      statistics: Record<string, number>;
      attack_progressions: unknown[];
      normal_baseline: Record<string, number>;
    }>("/sentinel-z/timeline"),
};

export { API_BASE };
