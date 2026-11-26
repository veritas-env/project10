"use client";

import { use, useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, errorMessage, fmtDate, RANK, type Location, type Product, type Transfer } from "@/lib/api";
import { useWorkspace, wsBase } from "@/lib/useWorkspace";

export default function TransfersPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const { workspace, error, setError } = useWorkspace(workspaceId);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [form, setForm] = useState({ product_id: "", from_location_id: "", to_location_id: "", quantity: "1" });
  const base = wsBase(workspaceId);

  const load = useCallback(() => {
    api<Transfer[]>(`${base}/transfers`).then(setTransfers).catch((e) => setError(errorMessage(e)));
    api<Product[]>(`${base}/products?limit=500`).then(setProducts).catch(() => {});
    api<Location[]>(`${base}/locations`).then(setLocations).catch(() => {});
  }, [base, setError]);
  useEffect(load, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api(`${base}/transfers`, { method: "POST", json: {
        product_id: form.product_id, from_location_id: form.from_location_id, to_location_id: form.to_location_id, quantity: Number(form.quantity) } });
      setForm({ ...form, quantity: "1" });
      load();
    } catch (err) { setError(errorMessage(err)); }
  }

  const canTransfer = workspace && RANK[workspace.role] >= RANK.member;
  const name = (id: string) => products.find((p) => p.id === id)?.sku ?? id.slice(0, 8);
  const loc = (id: string) => locations.find((l) => l.id === id)?.code ?? id.slice(0, 8);

  return (
    <Shell workspace={workspace}>
      <h1 className="mb-6">Stock transfers</h1>
      {error && <p className="error mb-4" role="alert">{error}</p>}
      {canTransfer && (
        <form onSubmit={create} className="card mb-6 flex flex-wrap items-end gap-3">
          <div><label className="label" htmlFor="p">Product</label>
            <select id="p" className="input" required value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })}>
              <option value="">Choose…</option>{products.map((p) => <option key={p.id} value={p.id}>{p.sku} · {p.name}</option>)}
            </select></div>
          <div><label className="label" htmlFor="fl">From</label>
            <select id="fl" className="input" required value={form.from_location_id} onChange={(e) => setForm({ ...form, from_location_id: e.target.value })}>
              <option value="">Choose…</option>{locations.map((l) => <option key={l.id} value={l.id}>{l.code}</option>)}
            </select></div>
          <div><label className="label" htmlFor="tl">To</label>
            <select id="tl" className="input" required value={form.to_location_id} onChange={(e) => setForm({ ...form, to_location_id: e.target.value })}>
              <option value="">Choose…</option>{locations.map((l) => <option key={l.id} value={l.id}>{l.code}</option>)}
            </select></div>
          <div><label className="label" htmlFor="qt">Quantity</label><input id="qt" className="input w-24" type="number" min="1" required value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></div>
          <button className="btn">Transfer</button>
        </form>
      )}
      <div className="card overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500">
            <tr><th className="px-4 py-2">Reference</th><th className="px-4 py-2">Product</th><th className="px-4 py-2">From → To</th><th className="px-4 py-2 text-right">Qty</th><th className="px-4 py-2">Status</th><th className="px-4 py-2">When</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {transfers.map((t) => (
              <tr key={t.id}>
                <td className="px-4 py-2 font-mono text-xs">{t.reference}</td>
                <td className="px-4 py-2 font-mono text-xs">{name(t.product_id)}</td>
                <td className="px-4 py-2 text-slate-600">{loc(t.from_location_id)} → {loc(t.to_location_id)}</td>
                <td className="px-4 py-2 text-right">{t.quantity}</td>
                <td className="px-4 py-2"><span className={`rounded px-2 py-0.5 text-xs ${t.status === "completed" ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-800"}`}>{t.status}</span></td>
                <td className="px-4 py-2 text-slate-500">{fmtDate(t.created_at)}</td>
              </tr>
            ))}
            {transfers.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">No transfers.</td></tr>}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
