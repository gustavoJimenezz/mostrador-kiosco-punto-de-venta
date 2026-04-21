/**
 * Vista de inyección de stock (F7).
 * Flujo: escanear/buscar producto → ingresar cantidad recibida → inyectar (suma al stock).
 */

import { useRef, useState } from 'react'
import { api } from '../../api/client'

interface Product { id: number; barcode: string; name: string; stock: number }
interface InjectionRecord { barcode: string; name: string; qty: number; newStock: number }

export default function StockInjectView() {
  const [search, setSearch] = useState('')
  const [results, setResults] = useState<Product[]>([])
  const [selected, setSelected] = useState<Product | null>(null)
  const [qty, setQty] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [history, setHistory] = useState<InjectionRecord[]>([])

  const searchRef = useRef<HTMLInputElement>(null)
  const qtyRef = useRef<HTMLInputElement>(null)

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMsg({ text, type })
    setTimeout(() => setMsg(null), 4000)
  }

  const focusQty = () => setTimeout(() => qtyRef.current?.focus(), 0)
  const focusSearch = () => setTimeout(() => searchRef.current?.focus(), 0)

  const pickProduct = (p: Product) => {
    setSelected(p)
    setResults([])
    setSearch('')
    setQty('')
    focusQty()
  }

  const reset = () => {
    setSelected(null)
    setResults([])
    setSearch('')
    setQty('')
    focusSearch()
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = search.trim()
    if (!q) return

    try {
      if (/^\d+$/.test(q)) {
        const product = await api.get<Product>(`/products/barcode/${q}`)
        pickProduct(product)
      } else {
        const found = await api.get<Product[]>(`/products/search?q=${encodeURIComponent(q)}`)
        if (found.length === 0) {
          showMsg(`No se encontró "${q}"`, 'error')
        } else if (found.length === 1) {
          pickProduct(found[0])
        } else {
          setResults(found)
        }
      }
    } catch {
      showMsg('Producto no encontrado', 'error')
    }
  }

  const handleInject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selected) return
    const amount = parseInt(qty)
    if (!amount || amount <= 0) return

    setSaving(true)
    try {
      const updated = await api.put<Product>(`/products/${selected.id}`, {
        stock: selected.stock + amount,
      })
      setHistory((prev) => [
        { barcode: selected.barcode, name: selected.name, qty: amount, newStock: updated.stock },
        ...prev,
      ])
      showMsg(`✓ ${selected.name}: +${amount} ud. (stock: ${updated.stock})`, 'success')
      reset()
    } catch (err: unknown) {
      showMsg(err instanceof Error ? err.message : 'Error al inyectar stock', 'error')
    } finally {
      setSaving(false)
    }
  }

  const amount = parseInt(qty) || 0

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="admin-content-header">
        <span className="admin-content-title">Inyectar Stock</span>
      </div>

      {msg && <div className={`msg msg-${msg.type}`}>{msg.text}</div>}

      {/* Panel de búsqueda e inyección */}
      <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Buscador */}
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8 }}>
          <input
            ref={searchRef}
            className="input"
            placeholder="Escanear código de barras o escribir nombre del producto…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setResults([]) }}
            autoFocus
            autoComplete="off"
            style={{ flex: 1 }}
          />
          <button type="submit" className="btn btn-primary">Buscar</button>
          {selected && (
            <button type="button" className="btn btn-secondary" onClick={reset}>Limpiar</button>
          )}
        </form>

        {/* Dropdown resultados nombre */}
        {results.length > 0 && (
          <div style={{ border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
            {results.map((p) => (
              <div
                key={p.id}
                onClick={() => pickProduct(p)}
                style={{
                  padding: '10px 14px', cursor: 'pointer', display: 'flex',
                  justifyContent: 'space-between', alignItems: 'center',
                  borderBottom: '1px solid var(--border)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = '')}
              >
                <span style={{ fontWeight: 500 }}>{p.name}</span>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                  {p.barcode} · Stock: {p.stock}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Formulario de inyección */}
        {selected && (
          <form onSubmit={handleInject}>
            <div style={{
              background: 'var(--bg-secondary)', borderRadius: 8, padding: '16px 20px',
              display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap',
            }}>
              {/* Info producto */}
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 2 }}>{selected.name}</div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  {selected.barcode}
                  <span style={{ margin: '0 8px' }}>·</span>
                  Stock actual: <strong style={{ color: 'var(--text-primary)' }}>{selected.stock}</strong>
                </div>
              </div>

              {/* Input cantidad */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <label style={{ fontWeight: 500, fontSize: 14, whiteSpace: 'nowrap' }}>
                  Cantidad recibida:
                </label>
                <input
                  ref={qtyRef}
                  type="number"
                  min="1"
                  className="input"
                  style={{ width: 90, textAlign: 'center', fontSize: 18, fontWeight: 700 }}
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                  placeholder="0"
                  required
                />
              </div>

              {/* Stock resultante */}
              {amount > 0 && (
                <div style={{ fontWeight: 600, color: 'var(--success)', fontSize: 15, whiteSpace: 'nowrap' }}>
                  → Nuevo stock: {selected.stock + amount}
                </div>
              )}

              <button
                type="submit"
                className="btn btn-success"
                disabled={saving || amount <= 0}
                style={{ whiteSpace: 'nowrap' }}
              >
                {saving ? 'Aplicando…' : 'Inyectar'}
              </button>
            </div>
          </form>
        )}

        {!selected && results.length === 0 && (
          <p style={{ color: 'var(--text-hint)', fontSize: 13, margin: 0 }}>
            Escaneá un código de barras o buscá por nombre para seleccionar el producto.
          </p>
        )}
      </div>

      {/* Historial de la sesión */}
      {history.length > 0 && (
        <div className="card scroll-y" style={{ padding: 0, flex: 1 }}>
          <div style={{ padding: '10px 16px', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid var(--border)' }}>
            Inyecciones de esta sesión
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Código</th>
                <th>Nombre</th>
                <th className="td-center">Inyectado</th>
                <th className="td-center">Stock resultante</th>
              </tr>
            </thead>
            <tbody>
              {history.map((r, i) => (
                <tr key={i}>
                  <td className="td-mono text-secondary">{r.barcode}</td>
                  <td style={{ fontWeight: 500 }}>{r.name}</td>
                  <td className="td-center font-bold text-success">+{r.qty}</td>
                  <td className="td-center font-bold">{r.newStock}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
