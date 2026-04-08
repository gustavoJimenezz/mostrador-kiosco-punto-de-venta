/**
 * Vista de historial de cierres de caja.
 * Muestra arqueos en un rango de fechas.
 */

import { useEffect, useState } from 'react'
import { api } from '../../api/client'

interface CashClose {
  id: number; opened_at: string; closed_at: string | null; is_open: boolean
  opening_amount: string; closing_amount: string | null
  total_sales_cash: string; total_sales_debit: string; total_sales_transfer: string
  total_sales: string; cash_difference: string | null
  gross_profit: string | null; total_cost_estimate: string | null; margin_percent: string | null
}

function today() { return new Date().toISOString().split('T')[0] }
function monthStart() {
  const d = new Date(); d.setDate(1)
  return d.toISOString().split('T')[0]
}
function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function CashHistoryView() {
  const [start, setStart] = useState(monthStart())
  const [end, setEnd] = useState(today())
  const [closes, setCloses] = useState<CashClose[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.get<CashClose[]>(`/cash/history?start=${start}&end=${end}`)
      setCloses(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al cargar historial')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const totalSales = closes.reduce((a, c) => a + parseFloat(c.total_sales), 0)
  const totalProfit = closes.reduce((a, c) => a + (c.gross_profit ? parseFloat(c.gross_profit) : 0), 0)

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="admin-content-header">
        <span className="admin-content-title">Historial de caja</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input type="date" className="input" value={start} onChange={(e) => setStart(e.target.value)} style={{ width: 150 }} />
          <span className="text-secondary">→</span>
          <input type="date" className="input" value={end} onChange={(e) => setEnd(e.target.value)} style={{ width: 150 }} />
          <button className="btn btn-secondary" onClick={load} disabled={loading}>Consultar</button>
        </div>
      </div>

      {error && <div className="msg msg-error">{error}</div>}

      {closes.length > 0 && (
        <div style={{ display: 'flex', gap: 12 }}>
          <div className="card" style={{ textAlign: 'center', flex: 1 }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Arqueos en el período</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--primary)' }}>{closes.length}</div>
          </div>
          <div className="card" style={{ textAlign: 'center', flex: 2 }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Ventas totales del período</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--success)' }}>${totalSales.toFixed(2)}</div>
          </div>
          <div className="card" style={{ textAlign: 'center', flex: 2 }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Ganancia bruta del período</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: totalProfit >= 0 ? 'var(--success)' : 'var(--danger)' }}>${totalProfit.toFixed(2)}</div>
          </div>
        </div>
      )}

      <div className="scroll-y card" style={{ padding: 0, flex: 1 }}>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-hint)' }}>Cargando…</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Apertura</th>
                <th>Cierre</th>
                <th>Estado</th>
                <th className="td-right">F.Inicial</th>
                <th className="td-right">Total ventas</th>
                <th className="td-right">Costo merc.</th>
                <th className="td-right">Ganancia</th>
                <th className="td-right">Margen</th>
                <th className="td-right">F.Contado</th>
                <th className="td-right">Diferencia</th>
              </tr>
            </thead>
            <tbody>
              {closes.length === 0 && (
                <tr><td colSpan={10} className="td-center" style={{ padding: '32px 0', color: 'var(--text-hint)' }}>Sin arqueos en el período</td></tr>
              )}
              {closes.map((c) => {
                const diff = c.cash_difference ? parseFloat(c.cash_difference) : null
                const profit = c.gross_profit ? parseFloat(c.gross_profit) : null
                return (
                  <tr key={c.id}>
                    <td className="td-mono">{fmtDateTime(c.opened_at)}</td>
                    <td className="td-mono">{c.closed_at ? fmtDateTime(c.closed_at) : '—'}</td>
                    <td>
                      <span className={`badge ${c.is_open ? 'badge-warning' : 'badge-secondary'}`}>
                        {c.is_open ? 'Abierta' : 'Cerrada'}
                      </span>
                    </td>
                    <td className="td-right td-mono">${c.opening_amount}</td>
                    <td className="td-right td-mono font-bold" style={{ color: 'var(--success)' }}>${c.total_sales}</td>
                    <td className="td-right td-mono text-secondary">{c.total_cost_estimate ? `$${c.total_cost_estimate}` : '—'}</td>
                    <td className={`td-right td-mono font-bold ${profit === null ? '' : profit >= 0 ? 'text-success' : 'text-danger'}`}>
                      {profit !== null ? `$${profit.toFixed(2)}` : '—'}
                    </td>
                    <td className="td-right td-mono text-secondary">{c.margin_percent ? `${c.margin_percent}%` : '—'}</td>
                    <td className="td-right td-mono">{c.closing_amount ? `$${c.closing_amount}` : '—'}</td>
                    <td className={`td-right td-mono font-bold ${diff === null ? '' : diff >= 0 ? 'text-success' : 'text-danger'}`}>
                      {diff !== null ? `${diff >= 0 ? '+' : ''}$${diff.toFixed(2)}` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
