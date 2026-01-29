'use client';

import { useState, useEffect, useMemo } from 'react';
import {
    Shield,
    ShieldAlert,
    Activity,
    Server,
    Cpu,
    FileText,
    AlertTriangle,
    ChevronLeft,
    ChevronRight,
    SkipForward,
    SkipBack,
    Filter,
    TrendingUp,
    Zap,
    Radio
} from 'lucide-react';
import { cn } from '@/lib/utils';

// --- Types ---
interface WindowData {
    window_id: number;
    start: string;
    end: string;
    label: number;
    num_nodes: number;
    num_edges: number;
    event_count: number;
}

interface GraphData {
    nodes: { id: string; node_type: string; degree?: number }[];
    links: { source: number; target: number; event?: string }[];
}

// --- Simple Mini Bar Chart (Pure CSS, no library needed) ---
function MiniBarChart({ data, highlightIndex }: { data: { value: number; isAttack: boolean }[]; highlightIndex?: number }) {
    const max = Math.max(...data.map(d => d.value), 1);

    return (
        <div className="flex items-end gap-[2px] h-16 w-full">
            {data.map((d, i) => {
                const height = (d.value / max) * 100;
                const isHighlighted = highlightIndex === i;
                return (
                    <div
                        key={i}
                        className={cn(
                            "flex-1 min-w-[3px] max-w-[8px] rounded-t transition-all duration-150",
                            d.isAttack ? "bg-red-500" : "bg-cyan-600",
                            isHighlighted && "ring-2 ring-white ring-offset-1 ring-offset-zinc-900"
                        )}
                        style={{ height: `${Math.max(height, 5)}%` }}
                        title={`Window ${i}: ${d.value} events${d.isAttack ? ' (ATTACK)' : ''}`}
                    />
                );
            })}
        </div>
    );
}

// --- Structure View Component ---
function StructureView({ graphData }: { graphData: GraphData }) {
    if (!graphData?.nodes?.length) {
        return <div className="text-zinc-500 p-8 text-center">No graph data available</div>;
    }

    const subjects = graphData.nodes.filter(n => n.node_type === 'subject');
    const objects = graphData.nodes.filter(n => n.node_type === 'object');

    return (
        <div className="h-full w-full overflow-y-auto p-4">
            <div className="grid grid-cols-2 gap-6">
                <div>
                    <h4 className="text-zinc-400 text-xs font-mono uppercase mb-3 flex items-center gap-2 sticky top-0 bg-zinc-950 py-2">
                        <Cpu size={14} className="text-amber-500" /> Active Processes ({subjects.length})
                    </h4>
                    <div className="space-y-1">
                        {subjects.slice(0, 25).map((node, i) => (
                            <div key={i} className="flex items-center gap-2 p-2 bg-zinc-900/50 border border-zinc-800 rounded text-xs hover:border-amber-500/50 transition-colors">
                                <div className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
                                <span className="font-mono text-zinc-300 truncate flex-1" title={node.id}>{node.id}</span>
                                {node.degree && <span className="text-zinc-600 text-[10px]">{node.degree}</span>}
                            </div>
                        ))}
                        {subjects.length > 25 && <div className="text-zinc-600 text-xs italic pl-2 py-2">+{subjects.length - 25} more processes</div>}
                    </div>
                </div>

                <div>
                    <h4 className="text-zinc-400 text-xs font-mono uppercase mb-3 flex items-center gap-2 sticky top-0 bg-zinc-950 py-2">
                        <FileText size={14} className="text-emerald-500" /> Accessed Files ({objects.length})
                    </h4>
                    <div className="space-y-1">
                        {objects.slice(0, 25).map((node, i) => (
                            <div key={i} className="flex items-center gap-2 p-2 bg-zinc-900/50 border border-zinc-800 rounded text-xs hover:border-emerald-500/50 transition-colors">
                                <div className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
                                <span className="font-mono text-zinc-300 truncate" title={node.id}>{node.id}</span>
                            </div>
                        ))}
                        {objects.length > 25 && <div className="text-zinc-600 text-xs italic pl-2 py-2">+{objects.length - 25} more files</div>}
                    </div>
                </div>
            </div>
        </div>
    );
}

// --- Main Dashboard ---
export default function Dashboard() {
    const [windows, setWindows] = useState<WindowData[]>([]);
    const [selectedWindow, setSelectedWindow] = useState<WindowData | null>(null);
    const [graphData, setGraphData] = useState<GraphData | null>(null);
    const [loading, setLoading] = useState(true);
    const [filterMode, setFilterMode] = useState<'all' | 'attacks'>('all');

    // Load Windows
    useEffect(() => {
        fetch('/api/windows')
            .then(res => res.json())
            .then(data => {
                if (Array.isArray(data)) {
                    setWindows(data);
                    const firstAttack = data.find(w => w.label === 1);
                    setSelectedWindow(firstAttack || data[0]);
                }
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    // Load Graph
    useEffect(() => {
        if (!selectedWindow) return;
        setGraphData(null);
        fetch(`/api/graph/${selectedWindow.window_id}`)
            .then(res => res.json())
            .then(data => {
                if (data?.nodes && data?.links) {
                    setGraphData(data);
                } else {
                    setGraphData({ nodes: [], links: [] });
                }
            })
            .catch(() => setGraphData({ nodes: [], links: [] }));
    }, [selectedWindow]);

    // Derived Data
    const attackWindows = useMemo(() => windows.filter(w => w.label === 1), [windows]);
    const filteredWindows = useMemo(() =>
        filterMode === 'attacks' ? attackWindows : windows,
        [windows, attackWindows, filterMode]
    );

    const chartData = useMemo(() =>
        windows.slice(0, 100).map(w => ({ value: w.event_count, isAttack: w.label === 1 })),
        [windows]
    );

    const currentIndex = useMemo(() =>
        windows.findIndex(w => w.window_id === selectedWindow?.window_id),
        [windows, selectedWindow]
    );

    // Navigation Functions
    const jumpToFirstAttack = () => {
        const first = attackWindows[0];
        if (first) setSelectedWindow(first);
    };

    const jumpToNextAttack = () => {
        const currentAttackIdx = attackWindows.findIndex(w => w.window_id === selectedWindow?.window_id);
        const nextAttack = attackWindows[currentAttackIdx + 1] || attackWindows[0];
        if (nextAttack) setSelectedWindow(nextAttack);
    };

    const jumpToPrevAttack = () => {
        const currentAttackIdx = attackWindows.findIndex(w => w.window_id === selectedWindow?.window_id);
        const prevAttack = attackWindows[currentAttackIdx - 1] || attackWindows[attackWindows.length - 1];
        if (prevAttack) setSelectedWindow(prevAttack);
    };

    const goNext = () => {
        const next = filteredWindows[filteredWindows.findIndex(w => w.window_id === selectedWindow?.window_id) + 1];
        if (next) setSelectedWindow(next);
    };

    const goPrev = () => {
        const prev = filteredWindows[filteredWindows.findIndex(w => w.window_id === selectedWindow?.window_id) - 1];
        if (prev) setSelectedWindow(prev);
    };

    const isAttack = selectedWindow?.label === 1;

    if (loading) {
        return (
            <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-zinc-500 font-mono text-sm">
                <Server className="animate-pulse mr-2" size={16} /> Initializing Sentinel Dashboard...
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-zinc-950 text-zinc-200 font-sans flex">

            {/* === LEFT SIDEBAR === */}
            <div className="w-80 border-r border-zinc-800 bg-zinc-900/50 flex flex-col">

                {/* Logo */}
                <div className="h-14 border-b border-zinc-800 flex items-center px-4 gap-3 bg-zinc-900">
                    <div className="w-8 h-8 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-lg flex items-center justify-center shadow-lg shadow-cyan-500/20">
                        <Shield size={18} className="text-white" />
                    </div>
                    <div>
                        <span className="font-bold tracking-tight text-white">SENTINEL-Z</span>
                        <div className="text-[10px] text-zinc-500">APT Detection System</div>
                    </div>
                </div>

                {/* Quick Stats */}
                <div className="p-3 border-b border-zinc-800 grid grid-cols-3 gap-2">
                    <div className="bg-zinc-800/50 p-2 rounded text-center">
                        <div className="text-lg font-bold text-white">{windows.length}</div>
                        <div className="text-[9px] text-zinc-500 uppercase">Windows</div>
                    </div>
                    <button
                        onClick={jumpToFirstAttack}
                        className="bg-red-950/50 border border-red-900/50 p-2 rounded text-center hover:bg-red-900/50 transition-colors"
                    >
                        <div className="text-lg font-bold text-red-400">{attackWindows.length}</div>
                        <div className="text-[9px] text-red-400/70 uppercase">Attacks</div>
                    </button>
                    <div className="bg-zinc-800/50 p-2 rounded text-center">
                        <div className="text-lg font-bold text-emerald-400">
                            {((1 - attackWindows.length / windows.length) * 100).toFixed(0)}%
                        </div>
                        <div className="text-[9px] text-zinc-500 uppercase">Safe</div>
                    </div>
                </div>

                {/* Event Timeline Chart */}
                <div className="p-3 border-b border-zinc-800">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] text-zinc-500 uppercase font-mono">Event Timeline</span>
                        <span className="text-[10px] text-zinc-600">{chartData.length} windows</span>
                    </div>
                    <MiniBarChart data={chartData} highlightIndex={currentIndex} />
                    <div className="flex justify-between text-[9px] text-zinc-600 mt-1">
                        <span>← Oldest</span>
                        <span>Recent →</span>
                    </div>
                </div>

                {/* Filter Toggle */}
                <div className="px-3 py-2 border-b border-zinc-800 flex gap-1">
                    <button
                        onClick={() => setFilterMode('all')}
                        className={cn(
                            "flex-1 text-xs py-1.5 rounded font-medium transition-colors",
                            filterMode === 'all' ? "bg-zinc-700 text-white" : "bg-zinc-800/50 text-zinc-500 hover:bg-zinc-800"
                        )}
                    >
                        All ({windows.length})
                    </button>
                    <button
                        onClick={() => setFilterMode('attacks')}
                        className={cn(
                            "flex-1 text-xs py-1.5 rounded font-medium transition-colors flex items-center justify-center gap-1",
                            filterMode === 'attacks' ? "bg-red-900/50 text-red-300" : "bg-zinc-800/50 text-zinc-500 hover:bg-zinc-800"
                        )}
                    >
                        <AlertTriangle size={12} /> Attacks ({attackWindows.length})
                    </button>
                </div>

                {/* Window List */}
                <div className="flex-1 overflow-y-auto">
                    {filteredWindows.map((w) => (
                        <button
                            key={w.window_id}
                            onClick={() => setSelectedWindow(w)}
                            className={cn(
                                "w-full text-left px-3 py-2.5 border-b transition-colors flex items-center gap-3",
                                selectedWindow?.window_id === w.window_id
                                    ? "bg-cyan-950/30 border-l-2 border-l-cyan-500 border-b-zinc-800"
                                    : w.label === 1
                                        ? "bg-red-950/10 border-b-zinc-800/50 hover:bg-red-950/20 border-l-2 border-l-red-500/50"
                                        : "bg-transparent border-b-zinc-800/50 hover:bg-zinc-800/30 border-l-2 border-l-transparent"
                            )}
                        >
                            <div className={cn(
                                "w-2 h-2 rounded-full flex-shrink-0",
                                w.label === 1 ? "bg-red-500 animate-pulse" : "bg-zinc-600"
                            )} />
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className="font-mono text-xs text-zinc-400">#{w.window_id.toString().padStart(4, '0')}</span>
                                    {w.label === 1 && (
                                        <span className="px-1 py-0.5 rounded text-[9px] font-bold bg-red-500/20 text-red-400">THREAT</span>
                                    )}
                                </div>
                                <div className="text-[11px] text-zinc-500 truncate">
                                    {w.start ? new Date(w.start).toLocaleTimeString() : 'N/A'} • {w.event_count} events
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* === MAIN CONTENT === */}
            <div className="flex-1 flex flex-col">

                {/* Top Toolbar */}
                <header className={cn(
                    "h-14 border-b flex items-center justify-between px-4 transition-colors duration-300",
                    isAttack ? "bg-red-950/30 border-red-900/30" : "bg-zinc-900/50 border-zinc-800"
                )}>
                    <div className="flex items-center gap-4">
                        {/* Navigation Controls */}
                        <div className="flex items-center gap-1 bg-zinc-800/50 rounded-lg p-1">
                            <button onClick={goPrev} className="p-1.5 hover:bg-zinc-700 rounded transition-colors" title="Previous">
                                <ChevronLeft size={16} />
                            </button>
                            <span className="text-xs font-mono text-zinc-400 px-2">
                                {filteredWindows.findIndex(w => w.window_id === selectedWindow?.window_id) + 1} / {filteredWindows.length}
                            </span>
                            <button onClick={goNext} className="p-1.5 hover:bg-zinc-700 rounded transition-colors" title="Next">
                                <ChevronRight size={16} />
                            </button>
                        </div>

                        {/* Attack Navigation */}
                        <div className="flex items-center gap-1 bg-red-950/30 border border-red-900/30 rounded-lg p-1">
                            <button onClick={jumpToPrevAttack} className="p-1.5 hover:bg-red-900/30 rounded transition-colors text-red-400" title="Previous Attack">
                                <SkipBack size={14} />
                            </button>
                            <button
                                onClick={jumpToFirstAttack}
                                className="px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-900/30 rounded transition-colors flex items-center gap-1"
                            >
                                <Zap size={12} /> Jump to Attack
                            </button>
                            <button onClick={jumpToNextAttack} className="p-1.5 hover:bg-red-900/30 rounded transition-colors text-red-400" title="Next Attack">
                                <SkipForward size={14} />
                            </button>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <div className={cn(
                            "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium",
                            isAttack ? "bg-red-900/30 text-red-300" : "bg-emerald-900/30 text-emerald-300"
                        )}>
                            {isAttack ? <ShieldAlert size={16} /> : <Activity size={16} />}
                            {isAttack ? "THREAT DETECTED" : "Normal Activity"}
                        </div>
                        <div className="text-xs font-mono text-zinc-500">
                            Window #{selectedWindow?.window_id?.toString().padStart(4, '0') ?? '----'}
                        </div>
                    </div>
                </header>

                {/* Content Area */}
                <div className="flex-1 grid grid-rows-[auto_1fr] gap-4 p-4 overflow-hidden">

                    {/* Stats Row */}
                    <div className="grid grid-cols-4 gap-4">
                        <div className={cn(
                            "p-4 rounded-lg border transition-colors",
                            isAttack ? "bg-red-950/20 border-red-900/30" : "bg-zinc-900/50 border-zinc-800"
                        )}>
                            <div className="flex items-center gap-2 mb-1">
                                <Radio size={14} className={isAttack ? "text-red-400" : "text-cyan-400"} />
                                <span className="text-xs text-zinc-500 uppercase">Events</span>
                            </div>
                            <div className="text-2xl font-bold">{selectedWindow?.event_count?.toLocaleString() ?? '0'}</div>
                        </div>

                        <div className={cn(
                            "p-4 rounded-lg border transition-colors",
                            isAttack ? "bg-red-950/20 border-red-900/30" : "bg-zinc-900/50 border-zinc-800"
                        )}>
                            <div className="flex items-center gap-2 mb-1">
                                <Cpu size={14} className="text-amber-400" />
                                <span className="text-xs text-zinc-500 uppercase">Nodes</span>
                            </div>
                            <div className="text-2xl font-bold">{selectedWindow?.num_nodes ?? 0}</div>
                        </div>

                        <div className={cn(
                            "p-4 rounded-lg border transition-colors",
                            isAttack ? "bg-red-950/20 border-red-900/30" : "bg-zinc-900/50 border-zinc-800"
                        )}>
                            <div className="flex items-center gap-2 mb-1">
                                <TrendingUp size={14} className="text-emerald-400" />
                                <span className="text-xs text-zinc-500 uppercase">Edges</span>
                            </div>
                            <div className="text-2xl font-bold">{selectedWindow?.num_edges ?? 0}</div>
                        </div>

                        <div className={cn(
                            "p-4 rounded-lg border transition-colors",
                            isAttack ? "bg-red-950/20 border-red-900/30" : "bg-zinc-900/50 border-zinc-800"
                        )}>
                            <div className="flex items-center gap-2 mb-1">
                                <Activity size={14} className={isAttack ? "text-red-400" : "text-zinc-400"} />
                                <span className="text-xs text-zinc-500 uppercase">Density</span>
                            </div>
                            <div className="text-2xl font-bold">
                                {selectedWindow && selectedWindow.num_nodes > 0
                                    ? (selectedWindow.num_edges / selectedWindow.num_nodes).toFixed(2)
                                    : '0.00'}
                            </div>
                        </div>
                    </div>

                    {/* Main Graph View */}
                    <div className={cn(
                        "rounded-lg border flex flex-col overflow-hidden transition-colors",
                        isAttack ? "bg-red-950/10 border-red-900/30" : "bg-zinc-900/30 border-zinc-800"
                    )}>
                        <div className={cn(
                            "h-10 border-b flex items-center justify-between px-4",
                            isAttack ? "bg-red-950/30 border-red-900/30" : "bg-zinc-900/50 border-zinc-800"
                        )}>
                            <span className="text-xs font-mono text-zinc-400 uppercase">Provenance Graph Structure</span>
                            <span className="text-xs text-zinc-600">
                                {graphData?.nodes?.length || 0} nodes • {graphData?.links?.length || 0} edges
                            </span>
                        </div>
                        <div className="flex-1 overflow-hidden bg-zinc-950">
                            {graphData ? (
                                <StructureView graphData={graphData} />
                            ) : (
                                <div className="flex h-full items-center justify-center text-zinc-500">
                                    <Server className="animate-pulse mr-2" size={16} /> Loading...
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Bottom Status Bar */}
                <div className={cn(
                    "h-8 border-t flex items-center justify-between px-4 text-xs font-mono transition-colors",
                    isAttack ? "bg-red-950/30 border-red-900/30 text-red-300" : "bg-zinc-900/50 border-zinc-800 text-zinc-500"
                )}>
                    <span>
                        Time Range: {selectedWindow?.start ? new Date(selectedWindow.start).toLocaleTimeString() : '--'} → {selectedWindow?.end ? new Date(selectedWindow.end).toLocaleTimeString() : '--'}
                    </span>
                    <span className="flex items-center gap-4">
                        <span>Press ← → to navigate</span>
                        <span className="flex items-center gap-1">
                            <div className={cn("w-2 h-2 rounded-full", isAttack ? "bg-red-500 animate-pulse" : "bg-emerald-500")} />
                            {isAttack ? "Threat Active" : "System Normal"}
                        </span>
                    </span>
                </div>
            </div>
        </div>
    );
}
