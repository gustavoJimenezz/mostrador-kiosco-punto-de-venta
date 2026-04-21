/**
 * Vista de historial de cierres de caja.
 *
 * Patrón master-detail:
 *   - Lista: tabla de arqueos con filtro por rango de fechas.
 *   - Detalle: al hacer clic en una fila, muestra el informe completo
 *     del arqueo seleccionado (ventas, rentabilidad, conciliación y
 *     movimientos manuales). Botón "← Volver" regresa a la lista.
 */

import { useEffect, useState } from 'react'
import { api } from '../../api/client'

interface CashClose {
  id: number
  opened_at: string
  closed_at: string | null
  is_open: boolean
  opening_amount: string
  closing_amount: string | null
  total_sales_cash: string
  total_sales_debit: string
  total_sales_transfer: string
  total_sales: string
  cash_difference: string | null
  gross_profit: string | null
  total_cost_estimate: string | null
  margin_percent: string | null
}

interface Movement {
  id: number
  cash_close_id: number
  amount: string
  description: string
  created_at: string
}

function today() { return new Date().toISOString().split('T')[0] }
function monthStart() {
  const d = new Date(); d.setDate(1)
  return d.toISOString().split('T')[0]
}
function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}
function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('es-AR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' })
}
function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

// ─── Subcomponente: detalle de un arqueo ──────────────────────────────────────

interface DetailProps {
  close: CashClose
  movements: Movement[]
  loadingMovements: boolean
  onBack: () => void
}

function CashCloseDetail({ close, movements, loadingMovements, onBack }: DetailProps) {
  const netMovements = movements.reduce((acc, m) => acc + parseFloat(m.amount), 0)
  const theoreticalCash = parseFloat(close.opening_amount) + parseFloat(close.total_sales_cash) + netMovements
  const diff = close.cash_difference ? parseFloat(close.cash_difference) : null
  const profit = close.gross_profit ? parseFloat(close.gross_profit) : null
  const margin = close.margin_percent ? parseFloat(close.margin_percent) : null

  return (
    <div className="cashclose-wrapper">

      {/* Encabezado */}
      <div className="cashclose-header">
        <button className="btn btn-secondary btn-sm" onClick={onBack}>← Volver al listado</button>
        <div className="cashclose-header-center">
          <div className="cashclose-header-title">Arqueo #{close.id}</div>
          <div className="cashclose-header-subtitle">
            {fmtDate(close.opened_at)}
            {' · '}
            <span className={`badge ${close.is_open ? 'badge-warning' : 'badge-secondary'}`}>
              {close.is_open ? 'Abierta' : 'Cerrada'}
            </span>
          </div>
        </div>
        <div style={{ width: 130 }} />
      </div>

      <div className="cashclose-body">

        {/* Resumen de horarios */}
        <div className="arqueo-section">
          <div className="arqueo-section-title">Horarios del arqueo</div>
          <div className="arqueo-row">
            <span>Apertura</span>
            <span className="font-mono">{fmtDateTime(close.opened_at)}</span>
          </div>
          <div className="arqueo-row">
            <span>Cierre</span>
            <span className="font-mono">{close.closed_at ? fmtDateTime(close.closed_at) : '—'}</span>
          </div>
        </div>

        {/* Rentabilidad */}
        <div className="arqueo-section">
          <div className="arqueo-section-title">
            Rentabilidad del Período{' '}
            <span style={{ fontWeight: 400, fontSize: 11 }}>(ganancia bruta estimada)</span>
          </div>
          {margin !== null && (
            <div style={{ background: 'var(--success-light)', borderRadius: 4, height: 10, marginBottom: 10, overflow: 'hidden' }}>
              <div style={{
                background: 'var(--success)', height: '100%',
                width: `${Math.min(margin, 100)}%`,
                borderRadius: 4, transition: 'width 0.4s ease',
              }} />
            </div>
          )}
          <div className="arqueo-row">
            <span>Total Facturado (Ventas)</span>
            <span className="font-mono">${close.total_sales}</span>
          </div>
          <div className="arqueo-row text-secondary">
            <span>(-) Costo de Mercadería vendida</span>
            <span className="font-mono">{close.total_cost_estimate ? `$${close.total_cost_estimate}` : '—'}</span>
          </div>
          <div className="arqueo-row" style={{ fontWeight: 700, color: profit !== null && profit >= 0 ? 'var(--success)' : 'var(--danger)' }}>
            <span>(=) Ganancia Bruta Estimada</span>
            <span className="font-mono">{profit !== null ? `$${profit.toFixed(2)}` : '—'}</span>
          </div>
          <div className="arqueo-row text-secondary">
            <span>Margen sobre ventas</span>
            <span className="font-mono">{margin !== null ? `${margin.toFixed(2)}%` : '—'}</span>
          </div>
        </div>

        {/* Ventas por método de pago */}
        <div className="arqueo-section">
          <div className="arqueo-section-title">Ventas por Método de Pago</div>
          <div className="arqueo-row">
            <span>Efectivo</span>
            <span className="font-mono">${close.total_sales_cash}</span>
          </div>
          <div className="arqueo-row">
            <span>Débito</span>
            <span className="font-mono">${close.total_sales_debit}</span>
          </div>
          <div className="arqueo-row">
            <span>Transferencia</span>
            <span className="font-mono">${close.total_sales_transfer}</span>
          </div>
          <div className="arqueo-row arqueo-row-total">
            <span>TOTAL VENTAS</span>
            <span className="font-mono">${close.total_sales}</span>
          </div>
        </div>

        {/* Conciliación de efectivo */}
        <div className="arqueo-section">
          <div className="arqueo-section-title">Conciliación de Efectivo</div>
          <div className="arqueo-row">
            <span>Monto Inicial (Apertura)</span>
            <span className="font-mono">${close.opening_amount}</span>
          </div>
          <div className="arqueo-row">
            <span>(+) Ventas en Efectivo</span>
            <span className="font-mono">${close.total_sales_cash}</span>
          </div>
          <div className="arqueo-row">
            <span>(+/-) Movimientos Manuales (neto)</span>
            <span className={`font-mono ${netMovements < 0 ? 'text-danger' : ''}`}>
              {loadingMovements ? '…' : `${netMovements >= 0 ? '+' : ''}$${netMovements.toFixed(2)}`}
            </span>
          </div>
          <div className="arqueo-row">
            <span>(=) Saldo Teórico en Caja</span>
            <span className="font-mono">{loadingMovements ? '…' : `$${theoreticalCash.toFixed(2)}`}</span>
          </div>
          {close.closing_amount && (
            <div className="arqueo-row">
              <span>Monto Contado (Real)</span>
              <span className="font-mono">${close.closing_amount}</span>
            </div>
          )}
          {diff !== null && (
            <div className="arqueo-row arqueo-row-diff">
              <span>Diferencia de Caja</span>
              <span className={`font-mono font-bold ${diff >= 0 ? 'text-success' : 'text-danger'}`}>
                {diff >= 0 ? '+' : ''}${diff.toFixed(2)} {diff >= 0 ? 'Sobrante' : 'Faltante'}
              </span>
            </div>
          )}
        </div>

        {/* Movimientos manuales */}
        <div className="arqueo-section">
          <div className="arqueo-section-title">Movimientos Manuales del Período</div>
          {loadingMovements ? (
            <p style={{ fontSize: 12, color: 'var(--text-hint)', fontStyle: 'italic', margin: 0 }}>Cargando movimientos…</p>
          ) : movements.length === 0 ? (
            <p style={{ fontSize: 12, color: 'var(--text-hint)', fontStyle: 'italic', margin: 0 }}>
              Sin movimientos manuales en este período.
            </p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: '5px 8px', color: 'var(--text-hint)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>Hora</th>
                  <th style={{ textAlign: 'left', padding: '5px 8px', color: 'var(--text-hint)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>Descripción</th>
                  <th style={{ textAlign: 'right', padding: '5px 8px', color: 'var(--text-hint)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>Monto</th>
                </tr>
              </thead>
              <tbody>
                {movements.map((m) => {
                  const positive = parseFloat(m.amount) >= 0
                  return (
                    <tr key={m.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '6px 8px', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{fmtTime(m.created_at)}</td>
                      <td style={{ padding: '6px 8px' }}>{m.description}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: positive ? 'var(--success)' : 'var(--danger)' }}>
                        {positive ? '+' : ''}${m.amount}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </div>
  )
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function CashHistoryView() {
  const [start, setStart] = useState(monthStart())
  const [end, setEnd] = useState(today())
  const [closes, setCloses] = useState<CashClose[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [selectedClose, setSelectedClose] = useState<CashClose | null>(null)
  const [selectedMovements, setSelectedMovements] = useState<Movement[]>([])
  const [loadingMovements, setLoadingMovements] = useState(false)

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

  const selectClose = async (c: CashClose) => {
    setSelectedClose(c)
    setSelectedMovements([])
    setLoadingMovements(true)
    try {
      const movs = await api.get<Movement[]>(`/cash/movements/${c.id}`)
      setSelectedMovements(movs)
    } catch {
      setSelectedMovements([])
    } finally {
      setLoadingMovements(false)
    }
  }

  const goBack = () => {
    setSelectedClose(null)
    setSelectedMovements([])
  }

  // ── Vista de detalle ──
  if (selectedClose) {
    return (
      <CashCloseDetail
        close={selectedClose}
        movements={selectedMovements}
        loadingMovements={loadingMovements}
        onBack={goBack}
      />
    )
  }

  // ── Vista de lista ──
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
                <th>#</th>
                <th>Apertura</th>
                <th>Cierre</th>
                <th>Estado</th>
                <th className="td-right">F.Inicial</th>
                <th className="td-right">Total ventas</th>
                <th className="td-right">Ganancia</th>
                <th className="td-right">Margen</th>
                <th className="td-right">Diferencia</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {closes.length === 0 && (
                <tr>
                  <td colSpan={10} className="td-center" style={{ padding: '32px 0', color: 'var(--text-hint)' }}>
                    Sin arqueos en el período
                  </td>
                </tr>
              )}
              {closes.map((c) => {
                const diff = c.cash_difference ? parseFloat(c.cash_difference) : null
                const profit = c.gross_profit ? parseFloat(c.gross_profit) : null
                return (
                  <tr
                    key={c.id}
                    style={{ cursor: 'pointer' }}
                    className="table-row-clickable"
                    onClick={() => selectClose(c)}
                    title="Ver detalle del arqueo"
                  >
                    <td className="td-mono text-secondary" style={{ fontSize: 11 }}>#{c.id}</td>
                    <td className="td-mono">{fmtDateTime(c.opened_at)}</td>
                    <td className="td-mono">{c.closed_at ? fmtDateTime(c.closed_at) : '—'}</td>
                    <td>
                      <span className={`badge ${c.is_open ? 'badge-warning' : 'badge-secondary'}`}>
                        {c.is_open ? 'Abierta' : 'Cerrada'}
                      </span>
                    </td>
                    <td className="td-right td-mono">${c.opening_amount}</td>
                    <td className="td-right td-mono font-bold" style={{ color: 'var(--success)' }}>${c.total_sales}</td>
                    <td className={`td-right td-mono font-bold ${profit === null ? '' : profit >= 0 ? 'text-success' : 'text-danger'}`}>
                      {profit !== null ? `$${profit.toFixed(2)}` : '—'}
                    </td>
                    <td className="td-right td-mono text-secondary">
                      {c.margin_percent ? `${parseFloat(c.margin_percent).toFixed(1)}%` : '—'}
                    </td>
                    <td className={`td-right td-mono font-bold ${diff === null ? '' : diff >= 0 ? 'text-success' : 'text-danger'}`}>
                      {diff !== null ? `${diff >= 0 ? '+' : ''}$${diff.toFixed(2)}` : '—'}
                    </td>
                    <td style={{ color: 'var(--primary)', fontSize: 12, paddingRight: 12 }}>Ver →</td>
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
