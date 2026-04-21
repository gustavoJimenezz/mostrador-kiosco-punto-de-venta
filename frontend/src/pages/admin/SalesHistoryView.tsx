/**
 * Vista de historial de ventas (F2 en panel admin).
 * Muestra ventas del día seleccionado con detalle de ítems por venta.
 * Permite cancelar ventas (solo admin) con restauración de stock.
 */

import React, { useEffect, useState } from 'react'
import { api } from '../../api/client'

interface SaleItem { product_name: string; quantity: number; price_at_sale: string; subtotal: string }
interface Sale {
  id: string
  timestamp: string
  total_amount: string
  payment_method: string
  is_cancelled: boolean
  cancelled_at: string | null
  items: SaleItem[]
}

const METHOD_LABEL: Record<string, string> = {
  EFECTIVO: 'Efectivo', DEBITO: 'Débito', TRANSFERENCIA: 'Transferencia',
}
const METHOD_BADGE: Record<string, string> = {
  EFECTIVO: 'badge-success', DEBITO: 'badge-info', TRANSFERENCIA: 'badge-warning',
}

function today() {
  return new Date().toISOString().split('T')[0]
}
function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function SalesHistoryView() {
  const [date, setDate] = useState(today())
  const [sales, setSales] = useState<Sale[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [cancelling, setCancelling] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError('')
    setExpanded(null)
    try {
      const data = await api.get<Sale[]>(`/sales?date=${date}`)
      setSales(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al cargar ventas')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [date])

  const handleCancel = async (sale: Sale) => {
    const confirm = window.confirm(
      `¿Cancelar esta venta de $${sale.total_amount}?\n` +
      `El stock de los productos será restaurado.`
    )
    if (!confirm) return

    setCancelling(sale.id)
    try {
      await api.delete(`/sales/${sale.id}`)
      await load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al cancelar la venta')
    } finally {
      setCancelling(null)
    }
  }

  // Solo ventas activas para totales del día
  const activeSales = sales.filter(s => !s.is_cancelled)
  const totalDay = activeSales.reduce((a, s) => a + parseFloat(s.total_amount), 0)
  const countByMethod = activeSales.reduce((acc, s) => {
    acc[s.payment_method] = (acc[s.payment_method] || 0) + parseFloat(s.total_amount)
    return acc
  }, {} as Record<string, number>)
  const cancelledCount = sales.filter(s => s.is_cancelled).length

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="admin-content-header">
        <span className="admin-content-title">Historial de ventas</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} style={{ width: 160 }} />
          <button className="btn btn-secondary" onClick={load} disabled={loading}>Actualizar</button>
        </div>
      </div>

      {error && <div className="msg msg-error">{error}</div>}

      {/* Resumen del día */}
      {sales.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          <div className="card" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Total ventas</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--success)' }}>${totalDay.toFixed(2)}</div>
            <div style={{ fontSize: 11, color: 'var(--text-hint)' }}>
              {activeSales.length} operacion{activeSales.length !== 1 ? 'es' : ''}
              {cancelledCount > 0 && <span style={{ color: 'var(--error)', marginLeft: 4 }}>({cancelledCount} cancelada{cancelledCount !== 1 ? 's' : ''})</span>}
            </div>
          </div>
          {Object.entries(countByMethod).map(([method, total]) => (
            <div key={method} className="card" style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{METHOD_LABEL[method] ?? method}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--primary)' }}>${total.toFixed(2)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabla de ventas */}
      <div className="scroll-y card" style={{ padding: 0, flex: 1 }}>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-hint)' }}>Cargando…</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Hora</th>
                <th>Método</th>
                <th>Ítems</th>
                <th className="td-right">Total</th>
                <th style={{ width: 120 }}></th>
              </tr>
            </thead>
            <tbody>
              {sales.length === 0 && (
                <tr><td colSpan={5} className="td-center" style={{ padding: '32px 0', color: 'var(--text-hint)' }}>Sin ventas para este día</td></tr>
              )}
              {sales.map((s) => (
                <React.Fragment key={s.id}>
                  <tr
                    style={{
                      cursor: 'pointer',
                      background: s.is_cancelled
                        ? 'var(--error-light, rgba(220,53,69,0.06))'
                        : hoveredId === s.id ? 'var(--primary-light)' : undefined,
                      opacity: s.is_cancelled ? 0.65 : 1,
                      transition: 'background 0.15s',
                    }}
                    onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                    onMouseEnter={() => setHoveredId(s.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    title={s.is_cancelled ? `Cancelada el ${fmtTime(s.cancelled_at!)}` : 'Click para ver detalle'}
                  >
                    <td className="td-mono text-secondary" style={s.is_cancelled ? { textDecoration: 'line-through' } : {}}>
                      {fmtTime(s.timestamp)}
                    </td>
                    <td>
                      {s.is_cancelled
                        ? <span className="badge badge-secondary">Cancelada</span>
                        : <span className={`badge ${METHOD_BADGE[s.payment_method] ?? 'badge-secondary'}`}>{METHOD_LABEL[s.payment_method] ?? s.payment_method}</span>
                      }
                    </td>
                    <td className="text-secondary">{s.items.length} ítem{s.items.length !== 1 ? 's' : ''}</td>
                    <td
                      className="td-right td-mono font-bold"
                      style={{ color: s.is_cancelled ? 'var(--text-hint)' : 'var(--primary)', textDecoration: s.is_cancelled ? 'line-through' : undefined }}
                    >
                      ${s.total_amount}
                    </td>
                    <td className="td-center text-secondary" style={{ fontSize: 11 }}>{expanded === s.id ? '▲ ocultar' : '▼ detalle'}</td>
                  </tr>
                  {expanded === s.id && (
                    <tr>
                      <td colSpan={5} style={{ padding: 0, background: s.is_cancelled ? 'rgba(220,53,69,0.04)' : 'var(--primary-light)' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <th style={{ padding: '4px 16px', textAlign: 'left', color: 'var(--text-secondary)' }}>Producto</th>
                              <th style={{ padding: '4px 8px', textAlign: 'center', color: 'var(--text-secondary)' }}>Cant.</th>
                              <th style={{ padding: '4px 8px', textAlign: 'right', color: 'var(--text-secondary)' }}>P.unit.</th>
                              <th style={{ padding: '4px 16px', textAlign: 'right', color: 'var(--text-secondary)' }}>Subtotal</th>
                            </tr>
                          </thead>
                          <tbody>
                            {s.items.map((item, i) => (
                              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                <td style={{ padding: '4px 16px' }}>{item.product_name}</td>
                                <td style={{ padding: '4px 8px', textAlign: 'center' }}>{item.quantity}</td>
                                <td style={{ padding: '4px 8px', textAlign: 'right', fontFamily: 'monospace' }}>${item.price_at_sale}</td>
                                <td style={{ padding: '4px 16px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700 }}>${item.subtotal}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!s.is_cancelled && (
                          <div style={{ padding: '8px 16px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end' }}>
                            <button
                              className="btn btn-danger"
                              style={{ fontSize: 12, padding: '4px 14px' }}
                              disabled={cancelling === s.id}
                              onClick={(e) => { e.stopPropagation(); handleCancel(s) }}
                            >
                              {cancelling === s.id ? 'Cancelando…' : 'Cancelar venta'}
                            </button>
                          </div>
                        )}
                        {s.is_cancelled && s.cancelled_at && (
                          <div style={{ padding: '6px 16px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--error, #dc3545)' }}>
                            Cancelada a las {fmtTime(s.cancelled_at)} — stock restaurado
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
