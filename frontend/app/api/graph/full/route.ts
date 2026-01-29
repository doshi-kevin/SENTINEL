import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
    const graphsDir = path.join(process.cwd(), '..', 'data', 'model_ready', 'graphs');

    try {
        // Read the first 50 graphs to create a "global" view for now
        // We limit this to prevent browser crashing with too many nodes
        const files = fs.readdirSync(graphsDir)
            .filter(f => f.endsWith('.json'))
            .slice(0, 50);

        let allNodes: any[] = [];
        let allLinks: any[] = [];
        let globalNodeIndex = 0;
        const nodeMap = new Map();

        for (const file of files) {
            const content = fs.readFileSync(path.join(graphsDir, file), 'utf-8');
            const data = JSON.parse(content);

            // Merge nodes
            for (const node of data.nodes) {
                if (!nodeMap.has(node.id)) {
                    // Add unique node
                    nodeMap.set(node.id, globalNodeIndex);
                    allNodes.push({
                        ...node,
                        globalId: globalNodeIndex
                    });
                    globalNodeIndex++;
                }
            }

            // Merge links
            for (const link of data.links) {
                // Find the new global indices for source/target
                // Note: The original JSON has local indices. 
                // We need to look up the node ID from the local index, then get the global index.
                const srcNode = data.nodes[link.source];
                const tgtNode = data.nodes[link.target];

                if (srcNode && tgtNode) {
                    const globalSrc = nodeMap.get(srcNode.id);
                    const globalTgt = nodeMap.get(tgtNode.id);

                    allLinks.push({
                        source: globalSrc,
                        target: globalTgt,
                        event: link.event
                    });
                }
            }
        }

        return NextResponse.json({
            nodes: allNodes,
            links: allLinks
        });

    } catch (error) {
        return NextResponse.json({ error: 'Failed to aggregate graphs' }, { status: 500 });
    }
}
