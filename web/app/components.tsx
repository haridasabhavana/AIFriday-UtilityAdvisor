"use client";

import React from "react";

export function LoadProfileChart({
  baseline,
  scenario,
}: {
  baseline: number[];
  scenario?: number[] | null;
}) {
  if (!baseline.length) return null;
  const maxVal = Math.max(...baseline, ...(scenario || [0]), 1.0) * 1.15;
  const W = 700;
  const H = 210;
  const padL = 40;
  const padR = 12;
  const padT = 16;
  const padB = 26;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const xFor = (i: number) => padL + (i / 23) * plotW;
  const yFor = (v: number) => padT + plotH - (v / maxVal) * plotH;

  const basePts = baseline.map((v, i) => `${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`).join(" ");
  const scenPts = scenario
    ? scenario.map((v, i) => `${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`).join(" ")
    : null;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block">
      {[0, 0.25, 0.5, 0.75, 1].map((f) => {
        const val = maxVal * f;
        const y = yFor(val);
        return (
          <g key={f}>
            <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="#e2e8f0" strokeWidth="1" />
            <text x={padL - 5} y={y + 3} textAnchor="end" fontSize="10" fill="#64748b">
              {val.toFixed(1)}
            </text>
          </g>
        );
      })}
      <rect x={xFor(18)} y={padT} width={xFor(21) - xFor(18)} height={plotH} fill="#f59e0b" fillOpacity="0.14" rx="4" />
      <text x={(xFor(18) + xFor(21)) / 2} y={padT + 12} textAnchor="middle" fontSize="10" fontWeight="700" fill="#b45309">
        PEAK 18–22h (₹10.20)
      </text>
      <polyline
        fill="none"
        stroke={scenPts ? "#94a3b8" : "#059669"}
        strokeWidth={scenPts ? 2 : 3}
        strokeDasharray={scenPts ? "5,4" : undefined}
        points={basePts}
      />
      {scenPts && <polyline fill="none" stroke="#059669" strokeWidth="3" points={scenPts} />}
      {[0, 4, 8, 12, 16, 18, 22].map((h) => (
        <text key={h} x={xFor(h)} y={H - 6} textAnchor="middle" fontSize="10" fill="#64748b">
          {String(h).padStart(2, "0")}:00
        </text>
      ))}
    </svg>
  );
}
