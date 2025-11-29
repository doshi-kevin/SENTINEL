import { generateStory } from "./story_generator.js";

console.log("GRAPH.JS LOADED");


const SVG = d3.select("#graphSvg");
const width = window.innerWidth * 0.70;     
const height = window.innerHeight * 0.70;   

SVG.attr("width", width).attr("height", height);

async function loadGraph() {
    const seqId = document.getElementById("seqInput").value;

    const graphRes = await fetch(`http://127.0.0.1:8000/graph/${seqId}`);
    const graph = await graphRes.json();

    const explainRes = await fetch(`http://127.0.0.1:8000/explain/${seqId}`);
    const explain = await explainRes.json();

    console.log("GRAPH:", graph);
    console.log("EXPLAIN:", explain);

    drawGraph(graph, explain);

    const story = generateStory(graph, explain);
    document.getElementById("storyContent").innerHTML = `
        <div class="story-section">
            <div class="story-title">Prediction:</div>
            <div>${story.prediction}</div>
        </div>

        <div class="story-section">
            <div class="story-title">Temporal Attention:</div>
            <div>${story.temporalSummary}</div>
        </div>

        <div class="story-section">
            <div class="story-title">Top Important Nodes:</div>
            <ul>
                ${story.topNodes
                    .map(n => `<li>${n.node} (${n.type}) — ${(n.score * 100).toFixed(2)}%</li>`)
                    .join("")}
            </ul>
        </div>

        <div class="story-section">
            <div class="story-title">Timeline:</div>
            <ul>${story.timeline.map(t => `<li>${t}</li>`).join("")}</ul>
        </div>
    `;
}

function drawGraph(graph, explain) {
    SVG.selectAll("*").remove();

    const panel = document.getElementById("infoPanel");
    panel.innerHTML = "<h3>Node Details</h3><p>Click a node to view info.</p>";

    const nodeImportance = explain.node_importance[1] || [];
    const maxImp = Math.max(...nodeImportance, 0.00001);

    const subjects = graph.nodes.filter(n => n.node_type_flag === 1);
    const objects = graph.nodes.filter(n => n.node_type_flag === 0);

    const colWidth = width / 3;

    subjects.forEach((n, i) => {
        n.x = colWidth * 0.7;
        n.y = 100 + i * 50;
    });

    objects.forEach((n, i) => {
        n.x = colWidth * 1.7;
        n.y = 100 + i * 50;
    });

    const links = graph.edges.map(e => ({
        source: graph.nodes.find(n => n.id === e.source),
        target: graph.nodes.find(n => n.id === e.target),
        event: e.event
    }));

    SVG.append("g")
        .selectAll("line")
        .data(links)
        .enter()
        .append("line")
        .attr("stroke", d => {
            if (d.event.includes("EXEC")) return "#ff4d4d";
            if (d.event.includes("WRITE")) return "#ffcc00";
            if (d.event.includes("READ")) return "#66ff66";
            if (d.event.includes("SEND")) return "#ff8800";
            return "#888";
        })
        .attr("stroke-width", 2)
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

    SVG.append("g")
        .selectAll("circle")
        .data(graph.nodes)
        .enter()
        .append("circle")
        .attr("r", 12)
        .attr("cx", d => d.x)
        .attr("cy", d => d.y)
        .attr("fill", (d, i) => {
            const score = nodeImportance[i] || 0;
            const heat = score / maxImp;
            if (heat > 0.6) return d3.interpolateReds(heat);
            return d.node_type_flag === 1 ? "#4da6ff" : "#cccccc";
        })
        .attr("stroke", "#fff")
        .attr("stroke-width", 2)
        .style("cursor", "pointer")
        .on("click", (event, d) => showNodeInfo(d, nodeImportance[graph.nodes.indexOf(d)], panel));
}

function showNodeInfo(node, importance, panel) {
    panel.innerHTML = `
        <h3>Node Details</h3>
        <p><b>ID:</b> ${node.id}</p>
        <p><b>Type:</b> ${node.node_type}</p>
        <p><b>Degree:</b> ${node.degree}</p>
        <p><b>Importance Score:</b> ${(importance || 0).toFixed(4)}</p>
        <hr>
        <pre>${JSON.stringify(node, null, 2)}</pre>
    `;
}

window.loadGraph = loadGraph;
