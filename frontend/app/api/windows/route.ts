import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  const labelsPath = path.join(process.cwd(), '..', 'data', 'model_ready', 'labels.csv');

  try {
    const content = fs.readFileSync(labelsPath, 'utf-8');
    const lines = content.trim().split('\n');

    const windows = lines.slice(1).map(line => {
      const [window_id, start, end, label, num_nodes, num_edges, event_count] = line.split(',');
      return {
        window_id: parseInt(window_id),
        start,
        end,
        label: parseInt(label),
        num_nodes: parseInt(num_nodes),
        num_edges: parseInt(num_edges),
        event_count: parseInt(event_count)
      };
    });

    return NextResponse.json(windows);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to load data' }, { status: 500 });
  }
}
