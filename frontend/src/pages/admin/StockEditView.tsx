/**
 * Vista de edición de stock (F6).
 * Permite modificar directamente el stock de cada producto.
 */

import { useEffect, useState } from 'react'
import { api } from '../../api/client'

interface Product { id: number; barcode: string; name: string; stock: number; min_stock: number }

interface EditRow { product_id: number; newStock: string }

export default function StockEditView() {
  const [products, setProducts] = useState<Product[]>([])
  const [edits, setEdits] = useState<Record<number, string>>({})
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const load = async () => {
    try {
      const data = await api.get<Product[]>('/products')
      setProducts(data)
      setEdits({})
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

  const handleSave = async () => {
    const rows: EditRow[] = Object.entries(edits).map(([id, val]) => ({
      product_id: parseInt(id),
      newStock: val,
    })).filter((r) => r.newStock !== '')

    if (rows.length === 0) return

    setSaving(true)
    let ok = 0; let fail = 0
    for (const row of rows) {
      try {
        await api.put(`/products/${row.product_id}`, { stock: parseInt(row.newStock) })
        ok++
      } catch { fail++ }
    }
    setSaving(false)

    if (fail > 0) showMsg(`${ok} actualizados, ${fail} fallidos`, 'error')
    else showMsg(`${ok} stock${ok !== 1 ? 's' : ''} actualizados correctamente`, 'success')

    await load()
  }

  const filtered = products.filter((p) =>
    !filter || p.name.toLowerCase().includes(filter.toLowerCase()) || p.barcode.includes(filter)
  )

  const changedCount = Object.keys(edits).length

  if (loading) return <div style={{ padding: 32, color: 'var(--text-secondary)' }}>Cargando...</div>

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {msg && <div className={`msg msg-${msg.type}`}>{msg.text}</div>}

      <div className="admin-content-header">
        <span className="admin-content-title">Editar Stock</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            className="input" placeholder="Buscar…"
            value={filter} onChange={(e) => setFilter(e.target.value)}
            style={{ width: 220 }}
          />
          {changedCount > 0 && (
            <span className="badge badge-info">{changedCount} pendiente{changedCount !== 1 ? 's' : ''}</span>
          )}
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={changedCount === 0 || saving}
          >
            {saving ? 'Guardando…' : `Guardar cambios (${changedCount})`}
          </button>
        </div>
      </div>

      <div className="msg msg-info" style={{ margin: 0 }}>
        Modificá el campo "Nuevo stock" para los productos que quieras actualizar y presioná <strong>Guardar cambios</strong>.
        Dejá el campo vacío para no modificar ese producto.
      </div>

      <div className="scroll-y card" style={{ padding: 0, flex: 1 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Código</th>
              <th>Nombre</th>
              <th className="td-center">Stock actual</th>
              <th className="td-center">Mín.</th>
              <th className="td-center">Nuevo stock</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={5} className="td-center" style={{ padding: '24px 0', color: 'var(--text-hint)' }}>Sin resultados</td></tr>
            )}
            {filtered.map((p) => (
              <tr key={p.id}>
                <td className="td-mono text-secondary">{p.barcode}</td>
                <td style={{ fontWeight: 500 }}>{p.name}</td>
                <td className={`td-center font-bold ${p.stock <= p.min_stock ? 'text-danger' : 'text-success'}`}>
                  {p.stock}
                </td>
                <td className="td-center text-secondary">{p.min_stock}</td>
                <td className="td-center" style={{ width: 120 }}>
                  <input
                    type="number"
                    min="0"
                    className="input"
                    style={{ textAlign: 'center', ...(edits[p.id] !== undefined ? { borderColor: 'var(--primary)', background: 'var(--primary-light)' } : {}) }}
                    placeholder={String(p.stock)}
                    value={edits[p.id] ?? ''}
                    onChange={(e) => {
                      const val = e.target.value
                      setEdits((prev) => {
                        if (val === '') {
                          const next = { ...prev }; delete next[p.id]; return next
                        }
                        return { ...prev, [p.id]: val }
                      })
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
