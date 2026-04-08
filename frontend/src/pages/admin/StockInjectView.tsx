/**
 * Vista de inyección de stock (F7).
 * Permite agregar unidades al stock existente de cada producto.
 */

import { useEffect, useState } from 'react'
import { api } from '../../api/client'

interface Product { id: number; barcode: string; name: string; stock: number; min_stock: number }

export default function StockInjectView() {
  const [products, setProducts] = useState<Product[]>([])
  const [injections, setInjections] = useState<Record<number, string>>({})
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const load = async () => {
    try {
      const data = await api.get<Product[]>('/products')
      setProducts(data)
      setInjections({})
    } catch {
      setMsg({ text: 'Error al cargar productos', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMsg({ text, type })
    setTimeout(() => setMsg(null), 3000)
  }

  const handleApply = async () => {
    const rows = products
      .filter((p) => injections[p.id] && parseInt(injections[p.id]) > 0)
      .map((p) => ({ product_id: p.id, inject: parseInt(injections[p.id]), current: p.stock }))

    if (rows.length === 0) return

    setSaving(true)
    let ok = 0; let fail = 0
    for (const row of rows) {
      try {
        await api.put(`/products/${row.product_id}`, { stock: row.current + row.inject })
        ok++
      } catch { fail++ }
    }
    setSaving(false)

    if (fail > 0) showMsg(`${ok} aplicados, ${fail} fallidos`, 'error')
    else showMsg(`Stock inyectado en ${ok} producto${ok !== 1 ? 's' : ''}`, 'success')

    await load()
  }

  const filtered = products.filter((p) =>
    !filter || p.name.toLowerCase().includes(filter.toLowerCase()) || p.barcode.includes(filter)
  )

  const pendingCount = Object.values(injections).filter((v) => v && parseInt(v) > 0).length

  if (loading) return <div style={{ padding: 32, color: 'var(--text-secondary)' }}>Cargando...</div>

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {msg && <div className={`msg msg-${msg.type}`}>{msg.text}</div>}

      <div className="admin-content-header">
        <span className="admin-content-title">Inyectar Stock</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            className="input" placeholder="Buscar…"
            value={filter} onChange={(e) => setFilter(e.target.value)}
            style={{ width: 220 }}
          />
          {pendingCount > 0 && (
            <span className="badge badge-info">{pendingCount} pendiente{pendingCount !== 1 ? 's' : ''}</span>
          )}
          <button
            className="btn btn-success"
            onClick={handleApply}
            disabled={pendingCount === 0 || saving}
          >
            {saving ? 'Aplicando…' : `Aplicar (${pendingCount})`}
          </button>
        </div>
      </div>

      <div className="msg msg-info" style={{ margin: 0 }}>
        Ingresá la <strong>cantidad a agregar</strong> en el campo correspondiente.
        El nuevo stock será stock actual + cantidad ingresada.
      </div>

      <div className="scroll-y card" style={{ padding: 0, flex: 1 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Código</th>
              <th>Nombre</th>
              <th className="td-center">Stock actual</th>
              <th className="td-center">Cantidad a agregar</th>
              <th className="td-center">Stock resultante</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={5} className="td-center" style={{ padding: '24px 0', color: 'var(--text-hint)' }}>Sin resultados</td></tr>
            )}
            {filtered.map((p) => {
              const inj = parseInt(injections[p.id] || '0') || 0
              const result = p.stock + inj
              return (
                <tr key={p.id}>
                  <td className="td-mono text-secondary">{p.barcode}</td>
                  <td style={{ fontWeight: 500 }}>{p.name}</td>
                  <td className={`td-center font-bold ${p.stock <= p.min_stock ? 'text-danger' : 'text-success'}`}>
                    {p.stock}
                  </td>
                  <td className="td-center" style={{ width: 140 }}>
                    <input
                      type="number"
                      min="0"
                      className="input"
                      style={{
                        textAlign: 'center',
                        ...(inj > 0 ? { borderColor: 'var(--success)', background: 'var(--success-light)' } : {}),
                      }}
                      placeholder="0"
                      value={injections[p.id] ?? ''}
                      onChange={(e) => {
                        const val = e.target.value
                        setInjections((prev) => {
                          if (val === '') { const next = { ...prev }; delete next[p.id]; return next }
                          return { ...prev, [p.id]: val }
                        })
                      }}
                    />
                  </td>
                  <td className={`td-center font-bold ${inj > 0 ? 'text-success' : 'text-secondary'}`}>
                    {inj > 0 ? result : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
