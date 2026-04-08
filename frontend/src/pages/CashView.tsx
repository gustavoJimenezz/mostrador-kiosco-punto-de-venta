/**
 * Vista de Movimientos de Caja.
 *
 * Registra ingresos y egresos manuales durante la sesión activa de caja.
 * Abrir / cerrar caja se gestiona desde los botones del header (App.tsx).
 */

import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface CashState {
  id: number | null
  is_open: boolean
  opened_at: string | null
  opening_amount: string
}

interface Movement {
  id: number
  cash_close_id: number
  amount: string
  description: string
  created_at: string
}

const emptyCashState: CashState = { id: null, is_open: false, opened_at: null, opening_amount: '0.00' }

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

function fmt(n: number) {
  return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function CashView() {
  const [cashState, setCashState] = useState<CashState>(emptyCashState)
  const [movements, setMovements] = useState<Movement[]>([])
  const [loading, setLoading] = useState(true)
  const [desc, setDesc] = useState('')
  const [amount, setAmount] = useState('0.01')
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const load = async () => {
    try {
      const state = await api.get<CashState>('/cash/state')
      setCashState(state)
      if (state.id) {
        const movs = await api.get<Movement[]>(`/cash/movements/${state.id}`)
        setMovements(movs)
      } else {
        setMovements([])
      }
    } catch {
      setMsg({ text: 'Error al cargar estado de caja', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMsg({ text, type })
    setTimeout(() => setMsg(null), 3500)
  }

  const handleMovement = async (sign: 1 | -1) => {
    if (!cashState.id || !desc.trim() || !amount) return
    setSubmitting(true)
    const finalAmount = (sign * Math.abs(parseFloat(amount))).toString()
    try {
      const m = await api.post<Movement>('/cash/movements', {
        cash_close_id: cashState.id,
        amount: finalAmount,
        description: desc.trim(),
      })
      setMovements((prev) => [...prev, m])
      setDesc('')
      setAmount('0.01')
      showMsg(`${sign > 0 ? 'Ingreso' : 'Egreso'} registrado correctamente`, 'success')
    } catch (err: unknown) {
      showMsg(err instanceof Error ? err.message : 'Error al registrar movimiento', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="loading">Cargando movimientos…</div>

  const netTotal = movements.reduce((acc, m) => acc + parseFloat(m.amount), 0)

  return (
    <div className="cashview-wrapper">
      {/* Banner informativo */}
      <div className="cashview-info-banner">
        <strong>Movimientos de caja</strong> — Registra ingresos y egresos manuales durante la sesión activa de caja.<br />
        <strong>+ Ingreso / − Egreso:</strong> registran el monto con la descripción ingresada. Solo disponibles con caja abierta.
      </div>

      {/* Sesión activa */}
      <div className="cashview-section">
        <div className="cashview-section-title">Sesión activa</div>
        {cashState.is_open && cashState.opened_at ? (
          <div className="cashview-session-open">
            ✓ Sesión abierta desde las {fmtTime(cashState.opened_at)}
            <span className="cashview-session-monto">(monto inicial: ${cashState.opening_amount})</span>
          </div>
        ) : (
          <div className="cashview-session-closed">
            ○ No hay ninguna sesión de caja abierta. Usá el botón <strong>Abrir caja</strong> del encabezado.
          </div>
        )}
      </div>

      {/* Tabla de movimientos */}
      <div className="cashview-section cashview-section-grow">
        <div className="cashview-section-title">Movimientos de la sesión</div>

        {msg && <div className={`msg msg-${msg.type}`} style={{ marginBottom: 8 }}>{msg.text}</div>}

        <div className="cashview-table-wrapper">
          <table className="cashview-table">
            <thead>
              <tr>
                <th style={{ width: 80 }}>Hora</th>
                <th>Descripción</th>
                <th style={{ width: 120, textAlign: 'right' }}>Monto</th>
              </tr>
            </thead>
            <tbody>
              {movements.length === 0 && (
                <tr>
                  <td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-hint)', padding: '40px 0', fontStyle: 'italic' }}>
                    Sin movimientos registrados en esta sesión.
                  </td>
                </tr>
              )}
              {movements.map((m) => {
                const positive = parseFloat(m.amount) >= 0
                return (
                  <tr key={m.id}>
                    <td className="font-mono text-secondary">{fmtTime(m.created_at)}</td>
                    <td>{m.description}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: positive ? 'var(--success)' : 'var(--danger)' }}>
                      {positive ? '+' : ''}${m.amount}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="cashview-total-neto">
          Total neto: <span className={`font-mono font-bold ${netTotal < 0 ? 'text-danger' : ''}`}>
            ${fmt(netTotal)}
          </span>
        </div>
      </div>

      {/* Formulario de registro */}
      {cashState.is_open && (
        <div className="cashview-register">
          <div className="cashview-section-title" style={{ marginBottom: 8 }}>Registrar movimiento</div>
          <div className="cashview-register-row">
            <input
              type="text"
              className="input"
              placeholder="Descripción del movimiento..."
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              style={{ flex: 1 }}
              onKeyDown={(e) => { if (e.key === 'Enter' && desc.trim()) handleMovement(1) }}
            />
            <input
              type="number"
              min="0.01"
              step="0.01"
              className="input font-mono"
              style={{ width: 100, textAlign: 'right' }}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            <button
              className="btn btn-success"
              disabled={submitting || !desc.trim() || !amount}
              onClick={() => handleMovement(1)}
            >
              + Ingreso
            </button>
            <button
              className="btn btn-danger"
              disabled={submitting || !desc.trim() || !amount}
              onClick={() => handleMovement(-1)}
            >
              − Egreso
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
