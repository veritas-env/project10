"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, use, useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, errorMessage, RANK, type Location, type Product } from "@/lib/api";
import { useWorkspace, wsBase } from "@/lib/useWorkspace";

function ProductsInner({ workspaceId }: { workspaceId: string }) {
  const search = useSearchParams();
  const { workspace, error, setError } = useWorkspace(workspaceId);
  const [products, setProducts] = useState<Product[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [q, setQ] = useState("");
  const [lowOnly, setLowOnly] = useState(search.get("low") === "1");
  const [form, setForm] = useState({ sku: "", name: "", reorder_level: "10" });
  const [adjust, setAdjust] = useState<{ product: Product; location_id: string; delta: string } | null>(null);
  const base = wsBase(workspaceId);

  const load = useCallback(() => {
    const qs = new URLSearchParams();
    if (q) qs.set("q", q);
    if (lowOnly) qs.set("low_stock", "true");
    api<Product[]>(`${base}/products?${qs}`).then(setProducts).catch((e) => setError(errorMessage(e)));
    api<Location[]>(`${base}/locations`).then(setLocations).catch(() => {});
  }, [base, q, lowOnly, setError]);
  useEffect(load, [load]);

  const canEdit = workspace && RANK[workspace.role] >= RANK.member;

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api(`${base}/products`, { method: "POST", json: { sku: form.sku, name: form.name, reorder_level: Number(form.reorder_level) } });
      setForm({ sku: "", name: "", reorder_level: "10" });
      load();
    } catch (err) { setError(errorMessage(err)); }
  }

  async function saveAdjust(e: React.FormEvent) {
    e.preventDefault();
    if (!adjust) return;
    try {
      await api(`${base}/products/${encodeURIComponent(adjust.product.id)}/adjust`, { method: "POST", json: { location_id: adjust.location_id, delta: Number(adjust.delta) } });
      setAdjust(null); load();
    } catch (err) { setError(errorMessage(err)); }
  }

  return (
    <Shell workspace={workspace}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1>Inventory</h1>
        <div className="flex items-center gap-3">
          <input className="input w-56" placeholder="Search name or SKU" maxLength={100} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
          <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={lowOnly} onChange={(e) => setLowOnly(e.target.checked)} /> Low stock only</label>
        </div>
      </div>
      {error && <p className="error mb-4" role="alert">{error}</p>}
      {canEdit && (
        <form onSubmit={create} className="card mb-6 flex flex-wrap items-end gap-3 p-4">
          <div><label className="label" htmlFor="sku">SKU</label><input id="sku" className="input w-32 font-mono uppercase" required pattern="[A-Z0-9-]{2,40}" value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value.toUpperCase() })} /></div>
          <div className="min-w-56 flex-1"><label className="label" htmlFor="n">Name</label><input id="n" className="input" required maxLength={160} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div><label className="label" htmlFor="rl">Reorder level</label><input id="rl" className="input w-28" type="number" min="0" value={form.reorder_level} onChange={(e) => setForm({ ...form, reorder_level: e.target.value })} /></div>
          <button className="btn">Add product</button>
        </form>
      )}
      <div className="card overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500">
            <tr><th className="px-4 py-2">SKU</th><th className="px-4 py-2">Product</th><th className="px-4 py-2">Locations</th><th className="px-4 py-2 text-right">Total</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {products.map((p) => (
              <tr key={p.id}>
                <td className="px-4 py-2 font-mono text-xs">{p.sku}</td>
                <td className="px-4 py-2">{p.name}<span className="ml-1 text-xs text-slate-400">/ {p.unit}</span></td>
                <td className="px-4 py-2 text-slate-600">{p.levels.map((l) => `${l.location_code}: ${l.quantity}`).join(", ") || "—"}</td>
                <td className={`px-4 py-2 text-right ${p.low_stock ? "font-semibold text-amber-700" : ""}`}>{p.total_quantity}</td>
                <td className="px-4 py-2 text-right">{canEdit && <button className="btn-quiet" onClick={() => setAdjust({ product: p, location_id: p.levels[0]?.location_id ?? locations[0]?.id ?? "", delta: "" })}>Adjust</button>}</td>
              </tr>
            ))}
            {products.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No products.</td></tr>}
          </tbody>
        </table>
      </div>
      {adjust && (
        <div className="fixed inset-0 z-10 flex items-center justify-center bg-slate-900/30" onClick={() => setAdjust(null)}>
          <form onSubmit={saveAdjust} className="card w-full max-w-sm space-y-3" onClick={(e) => e.stopPropagation()}>
            <h2>Adjust {adjust.product.sku}</h2>
            <select className="input" value={adjust.location_id} onChange={(e) => setAdjust({ ...adjust, location_id: e.target.value })} aria-label="Location">
              {locations.map((l) => <option key={l.id} value={l.id}>{l.code} — {l.name}</option>)}
            </select>
            <input className="input" type="number" required placeholder="Change, e.g. 20 or -5" value={adjust.delta} onChange={(e) => setAdjust({ ...adjust, delta: e.target.value })} aria-label="Change" />
            <div className="flex justify-end gap-2"><button type="button" className="btn-quiet" onClick={() => setAdjust(null)}>Cancel</button><button className="btn">Save</button></div>
          </form>
        </div>
      )}
    </Shell>
  );
}

export default function ProductsPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  return <Suspense><ProductsInner workspaceId={workspaceId} /></Suspense>;
}
