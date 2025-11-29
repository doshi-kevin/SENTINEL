export function generateStory(graph, explanation) {
    const prediction = explanation.prediction === 1 ? "MALICIOUS" : "BENIGN";
    const temporal = explanation.temporal_attention;

    // Temporal reasoning summary
    const temporalSummary = `T1: ${(temporal[0] * 100).toFixed(1)}% | T2: ${(temporal[1] * 100).toFixed(1)}% | T3: ${(temporal[2] * 100).toFixed(1)}%`;

    // Compute top node importances
    let nodeScores = [];
    explanation.node_importance.forEach((seq, tIndex) => {
        seq.forEach((score, nIndex) => {
            nodeScores.push({
                node: graph.nodes[nIndex]?.id,
                type: graph.nodes[nIndex]?.node_type,
                score
            });
        });
    });

    nodeScores.sort((a, b) => b.score - a.score);
    const topNodes = nodeScores.slice(0, 5);

    // Build timeline based on event timestamps
    const events = graph.edges
        .map(e => ({
            ts: new Date(e.ts),
            src: e.source,
            tgt: e.target,
            event: e.event
        }))
        .sort((a, b) => a.ts - b.ts);

    const timeline = events.map(e =>
        `${e.ts.toLocaleTimeString()} → ${e.src} ${e.event} ${e.tgt}`
    );

    return { prediction, temporalSummary, topNodes, timeline };
}
