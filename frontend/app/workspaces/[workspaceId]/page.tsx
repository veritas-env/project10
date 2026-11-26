"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, errorMessage, timeAgo, type Dashboard } from "@/lib/api";
import { useWorkspace, wsBase } from "@/lib/useWorkspace";

export default function OverviewPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const { workspace, error, setError } = useWorkspace(workspaceId);
  const [d, setD] = useState<Dashboard | null>(null);

  useEffect(() => {
    api<Dashboard>(`${wsBase(workspaceId)}/dashboard`).then(setD).catch((e) => setError(errorMessage(e)));
  }, [workspaceId, setError]);

  const base = `/workspaces/${encodeURIComponent(workspaceId)}`;
  return (
    <Shell workspace={workspace}>
      <h1 className="mb-6">Overview</h1>
      {error && <p className="error mb-4">{error}</p>}
      {d && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-5">
            <Link href={`${base}/products`} className="card p-4 hover:border-teal-300"><div className="text-2xl font-semibold">{d.products}</div><div className="text-xs text-slate-500">Products</div></Link>
            <div className="card p-4"><div className="text-2xl font-semibold">{d.total_units.toLocaleString()}</div><div className="text-xs text-slate-500">Units in stock</div></div>
            <div className="card p-4"><div className="text-2xl font-semibold">{d.locations}</div><div className="text-xs text-slate-500">Locations</div></div>
            <Link href={`${base}/products?low=1`} className="card p-4 hover:border-teal-300"><div className={`text-2xl font-semibold ${d.low_stock ? "text-amber-700" : ""}`}>{d.low_stock}</div><div className="text-xs text-slate-500">Low stock</div></Link>
            <div className="card p-4"><div className="text-2xl font-semibold">{d.open_purchase_orders}</div><div className="text-xs text-slate-500">Open POs</div></div>
          </div>
          <section className="card">
            <h2 className="mb-3">Recent activity</h2>
            {d.recent_activity.length === 0 && <p className="text-sm text-slate-500">No activity yet.</p>}
            <ul className="divide-y divide-slate-100 text-sm">
              {d.recent_activity.map((a) => (
                <li key={a.id} className="flex justify-between gap-4 py-2">
                  <span><span className="font-medium">{a.actor_name ?? "Someone"}</span> {a.summary}</span>
                  <time className="shrink-0 text-xs text-slate-500">{timeAgo(a.at)}</time>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </Shell>
  );
}
