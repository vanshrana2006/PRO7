"use client";

import { useMemo } from "react";

interface Node {
  x: number;
  y: number;
  r: number;
  delay: number;
  duration: number;
}

interface Edge {
  from: number;
  to: number;
}

/**
 * Ambient background rendering the product's core metaphor directly: a
 * knowledge graph as a star chart. Papers/entities are stars, the
 * relationships extracted between them are the connecting lines -- this
 * is literally what the platform builds, not decoration borrowed from
 * elsewhere. Nodes twinkle and drift slowly; kept subtle (low opacity,
 * behind glass panels) so it reads as atmosphere, not noise.
 *
 * Pure SVG + CSS animation -- no canvas/three.js dependency, deterministic
 * seeded layout so server and client render identically (avoids
 * hydration mismatches from Math.random on each render).
 */
function seededRandom(seed: number) {
  let value = seed;
  return () => {
    value = (value * 9301 + 49297) % 233280;
    return value / 233280;
  };
}

function generateGraph(nodeCount: number, seed: number): { nodes: Node[]; edges: Edge[] } {
  const rand = seededRandom(seed);
  const nodes: Node[] = Array.from({ length: nodeCount }, () => ({
    x: rand() * 100,
    y: rand() * 100,
    r: 1 + rand() * 1.8,
    delay: rand() * 4,
    duration: 3 + rand() * 3,
  }));

  const edges: Edge[] = [];
  nodes.forEach((node, i) => {
    // Connect each node to its nearest 1-2 neighbors for a natural,
    // non-uniform constellation look rather than a grid.
    const distances = nodes
      .map((other, j) => ({ j, d: Math.hypot(node.x - other.x, node.y - other.y) }))
      .filter((d) => d.j !== i)
      .sort((a, b) => a.d - b.d);

    const connections = distances.slice(0, rand() > 0.6 ? 2 : 1);
    connections.forEach(({ j }) => {
      if (!edges.some((e) => (e.from === i && e.to === j) || (e.from === j && e.to === i))) {
        edges.push({ from: i, to: j });
      }
    });
  });

  return { nodes, edges };
}

export function ConstellationBackground({ seed = 42, nodeCount = 60 }: { seed?: number; nodeCount?: number }) {
  const { nodes, edges } = useMemo(() => generateGraph(nodeCount, seed), [nodeCount, seed]);

  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-void">
      <div
        className="absolute inset-0 opacity-90"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(44,122,110,0.18), transparent 60%), radial-gradient(ellipse 60% 50% at 90% 100%, rgba(138,100,37,0.10), transparent 60%)",
        }}
      />
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 h-full w-full animate-drift"
      >
        <g stroke="rgba(94,234,212,0.15)" strokeWidth="0.08">
          {edges.map((e, i) => (
            <line
              key={i}
              x1={nodes[e.from].x}
              y1={nodes[e.from].y}
              x2={nodes[e.to].x}
              y2={nodes[e.to].y}
            />
          ))}
        </g>
        <g fill="#5EEAD4">
          {nodes.map((n, i) => (
            <circle
              key={i}
              cx={n.x}
              cy={n.y}
              r={n.r * 0.25}
              className="animate-twinkle"
              style={{
                animationDelay: `${n.delay}s`,
                animationDuration: `${n.duration}s`,
              }}
            />
          ))}
        </g>
      </svg>
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-void" />
    </div>
  );
}
