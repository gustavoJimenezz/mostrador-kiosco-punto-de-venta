/**
 * Vista de Cierre de Caja.
 *
 * Se muestra como pestaña independiente al hacer clic en "Cierre de caja".
 * Carga sus propios datos al montar y gestiona el flujo de cierre completo.
 */

import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface CashState {
  id: number | null
  is_open: boolean
  opened_at: string | null
  opening_amount: string
  total_sales_cash: string
  total_sales_debit: string
  total_sales_transfer: string
  total_sales: string
  expected_cash: string
}

interface Movement {
  id: number
  cash_close_id: number
  amount: string
  description: string
  created_at: string
}

interface ProfitData {
  total_revenue: string
  total_cost_estimate: string
  gross_profit: string
  margin_percent: string
  total_sales_count: number
}

interface Props {
  userName: string
  onBack: () => void
  onClosed: () => void
}

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

export default function CashCloseView({ userName, onBack, onClosed }: Props) {
  const [cashState, setCashState] = useState<CashState | null>(null)
  const [movements, setMovements] = useState<Movement[]>([])
  const [profitData, setProfitData] = useState<ProfitData | null>(null)
  const [closingAmount, setClosingAmount] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [closed, setClosed] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const [state, profit] = await Promise.all([
          api.get<CashState>('/cash/state'),
          api.get<ProfitData>('/cash/profit'),
        ])
        setCashState(state)
        setProfitData(profit)
        if (state.id) {
          const movs = await api.get<Movement[]>(`/cash/movements/${state.id}`)
          setMovements(movs)
        }
      } catch {
        setMsg({ text: 'Error al cargar datos de caja', type: 'error' })
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleClose = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!closingAmount) return
    setSubmitting(true)
    setMsg(null)
    try {
      await api.post('/cash/close', { closing_amount: closingAmount })
      setClosed(true)
    } catch (err: unknown) {
      setMsg({ text: err instanceof Error ? err.message : 'Error al cerrar caja', type: 'error' })
      setSubmitting(false)
    }
  }

  if (loading) return <div className="loading">Cargando datos de cierre…</div>

  if (!cashState?.is_open) {
    return (
      <div className="cashclose-wrapper">
        <div className="cashclose-header">
          <button className="btn btn-secondary btn-sm" onClick={onBack}>← Volver</button>
          <span className="cashclose-header-title">Cierre de Caja</span>
          <div style={{ width: 80 }} />
        </div>
        <div style={{ padding: 24 }}>
          <div className="msg msg-error">No hay ningún arqueo de caja abierto.</div>
        </div>
      </div>
    )
  }

  const netMovements = movements.reduce((acc, m) => acc + parseFloat(m.amount), 0)
  const theoreticalCash = parseFloat(cashState.expected_cash) + netMovements
  const countedAmount = parseFloat(closingAmount) || 0
  const difference = countedAmount - theoreticalCash
  const differenceLabel = difference >= 0 ? 'Sobrante' : 'Faltante'

  return (
    <div className="cashclose-wrapper">

      {/* ── Encabezado fijo ── */}
      <div className="cashclose-header">
        <button className="btn btn-secondary btn-sm" onClick={onBack}>← Volver</button>
        <div className="cashclose-header-center">
          <div className="cashclose-header-title">Informe de Cierre de Caja</div>
          {cashState.opened_at && (
            <div className="cashclose-header-subtitle">
              Apertura: {fmtDateTime(cashState.opened_at)} · Operador: {userName}
            </div>
          )}
        </div>
        <div style={{ width: 80 }} />
      </div>

      {/* ── Cuerpo scrollable ── */}
      <div className="cashclose-body">

        {/* Rentabilidad */}
        <div className="arqueo-section">
          <div className="arqueo-section-title">
            Rentabilidad del Período{' '}
            <span style={{ fontWeight: 400, fontSize: 11 }}>(ganancia bruta estimada)</span>
          </div>
          {profitData && (
            <div style={{ background: 'var(--success-light)', borderRadius: 4, height: 10, marginBottom: 10, overflow: 'hidden' }}>
              <div style={{
                background: 'var(--success)', height: '100%',
                width: `${Math.min(parseFloat(profitData.margin_percent), 100)}%`,
                borderRadius: 4, transition: 'width 0.4s ease',
              }} />
            </div>
          )}
          <div className="arqueo-row">
            <span>Total Facturado (Ventas)</span>
            <span className="font-mono">${profitData ? profitData.total_revenue : cashState.total_sales}</span>
          </div>
          <div className="arqueo-row text-secondary">
            <span>(-) Costo de Mercadería vendida *</span>
            <span className="font-mono">{profitData ? `$${profitData.total_cost_estimate}` : '…'}</span>
          </div>
          <div className="arqueo-row" style={{ fontWeight: 700, color: 'var(--success)' }}>
            <span>(=) Ganancia Bruta Estimada</span>
            <span className="font-mono">{profitData ? `$${profitData.gross_profit}` : '…'}</span>
          </div>
          <div className="arqueo-row text-secondary">
            <span>Margen sobre ventas</span>
            <span className="font-mono">{profitData ? `${profitData.margin_percent}%` : '—'}</span>
          </div>
          <div className="arqueo-row text-secondary">
            <span>Cantidad de ventas del período</span>
            <span className="font-mono">{profitData?.total_sales_count ?? 0}</span>
          </div>
        </div>

        {/* Ventas por método de pago */}
        <div className="arqueo-section">
          <div className="arqueo-section-title">Ventas del Período por Método de Pago</div>
          <div className="arqueo-row"><span>Efectivo</span><span className="font-mono">${cashState.total_sales_cash}</span></div>
          <div className="arqueo-row"><span>Débito</span><span className="font-mono">${cashState.total_sales_debit}</span></div>
          <div className="arqueo-row"><span>Transferencia</span><span className="font-mono">${cashState.total_sales_transfer}</span></div>
          <div className="arqueo-row arqueo-row-total">
            <span>TOTAL VENTAS</span>
            <span className="font-mono">${cashState.total_sales}</span>
          </div>
        </div>

        {/* Conciliación de efectivo + formulario de cierre */}
        <div className="arqueo-section">
          <div className="arqueo-section-title">Conciliación de Efectivo</div>
          <div className="arqueo-row">
            <span>Monto Inicial (Apertura)</span>
            <span className="font-mono">${cashState.opening_amount}</span>
          </div>
          <div className="arqueo-row">
            <span>(+) Ventas en Efectivo</span>
            <span className="font-mono">${cashState.total_sales_cash}</span>
          </div>
          <div className="arqueo-row">
            <span>(+/-) Movimientos Manuales (neto)</span>
            <span className={`font-mono ${netMovements < 0 ? 'text-danger' : ''}`}>
              {netMovements >= 0 ? '+' : ''}${netMovements.toFixed(2)}
            </span>
          </div>
          <div className="arqueo-row">
            <span>(=) Saldo Teórico en Caja</span>
            <span className="font-mono">${theoreticalCash.toFixed(2)}</span>
          </div>

          {!closed ? (
            <form onSubmit={handleClose}>
              <div className="cashclose-counted-row">
                <span>Monto Contado (Real)</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="input font-mono"
                  style={{ width: 160, textAlign: 'right' }}
                  value={closingAmount}
                  onChange={(e) => setClosingAmount(e.target.value)}
                  placeholder="0.00"
                  required
                  autoFocus
                />
              </div>

              {closingAmount && (
                <div className="arqueo-row arqueo-row-diff">
                  <span>Diferencia de Caja</span>
                  <span className={`font-mono font-bold ${difference >= 0 ? 'text-success' : 'text-danger'}`}>
                    ${Math.abs(difference).toFixed(2)} {differenceLabel}
                  </span>
                </div>
              )}

              {/* Movimientos manuales */}
              <div className="arqueo-section" style={{ marginTop: 14 }}>
                <div className="arqueo-section-title">Movimientos Manuales del Período</div>
                {movements.length === 0 ? (
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

              {msg && (
                <div className={`msg msg-${msg.type}`} style={{ marginTop: 12 }}>
                  {msg.text}
                </div>
              )}

              {/* Acciones */}
              <div className="cashclose-actions">
                <button type="button" className="btn btn-secondary" onClick={onBack} disabled={submitting}>
                  ← Volver
                </button>
                <button type="submit" className="btn btn-danger" disabled={submitting || !closingAmount}>
                  {submitting ? 'Cerrando…' : 'Confirmar y cerrar caja'}
                </button>
              </div>
            </form>
          ) : (
            <>
              <div className="arqueo-row arqueo-row-diff">
                <span>Monto Contado (Real)</span>
                <span className="font-mono font-bold">${parseFloat(closingAmount).toFixed(2)}</span>
              </div>
              <div className="arqueo-row arqueo-row-diff">
                <span>Diferencia de Caja</span>
                <span className={`font-mono font-bold ${difference >= 0 ? 'text-success' : 'text-danger'}`}>
                  ${Math.abs(difference).toFixed(2)} {differenceLabel}
                </span>
              </div>
              <div className="msg msg-success" style={{ marginTop: 16 }}>
                ✓ Caja cerrada correctamente.
              </div>
              <div className="cashclose-actions">
                <button className="btn btn-secondary" onClick={onClosed}>
                  ← Volver al inicio
                </button>
              </div>
            </>
          )}
        </div>

      </div>
    </div>
  )
}
