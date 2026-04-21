/**
 * Diálogo de confirmación de cobro (F4 / F12).
 * Permite seleccionar el método de pago. Para Efectivo, calcula el vuelto.
 */

import { useEffect, useRef, useState } from 'react'
import { calculateChange, formatCents } from '../utils/changeCalc'

interface Props {
  total: string
  onConfirm: (paymentMethod: string, changeCents: number) => void
  onCancel: () => void
}

const METHODS = [
  { value: 'EFECTIVO', label: 'Efectivo' },
  { value: 'DEBITO', label: 'Débito' },
  { value: 'TRANSFERENCIA', label: 'Transferencia' },
]

export default function ChangeDialog({ total, onConfirm, onCancel }: Props) {
  const [received, setReceived] = useState(total)
  const [method, setMethod] = useState('EFECTIVO')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (method === 'EFECTIVO') {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [method])

  const changeCents = method === 'EFECTIVO' ? calculateChange(total, received) : 0
  const canConfirm = method !== 'EFECTIVO' || changeCents >= 0

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
      if (e.key === 'Enter') {
        e.preventDefault()
        if (canConfirm) onConfirm(method, changeCents)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [received, canConfirm, changeCents, method])

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 400 }}>
        <div className="modal-title">Confirmar cobro</div>

        {/* Selector de método de pago */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {METHODS.map((m) => (
            <button
              key={m.value}
              type="button"
              className={`btn ${method === m.value ? 'btn-success' : 'btn-secondary'} btn-sm`}
              style={{ flex: 1 }}
              onClick={() => setMethod(m.value)}
            >
              {m.label}
            </button>
          ))}
        </div>

        <div className="groupbox" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>Total a cobrar</span>
            <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--success)' }}>${total}</span>
          </div>
        </div>

        {method === 'EFECTIVO' && (
          <>
            <div className="form-group">
              <label className="form-label">Monto recibido ($)</label>
              <input
                ref={inputRef}
                type="number"
                min="0"
                step="0.01"
                className="input input-lg"
                value={received}
                onChange={(e) => setReceived(e.target.value)}
                placeholder="0.00"
              />
            </div>

            <div
              className="groupbox"
              style={{
                background: canConfirm ? 'var(--success-light)' : 'var(--danger-light)',
                border: `1px solid ${canConfirm ? 'var(--success)' : 'var(--danger)'}`,
                marginBottom: 0,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 600, color: canConfirm ? 'var(--success)' : 'var(--danger)' }}>
                  {canConfirm ? 'Vuelto' : 'Falta'}
                </span>
                <span style={{ fontSize: 24, fontWeight: 700, color: canConfirm ? 'var(--success)' : 'var(--danger)' }}>
                  ${formatCents(changeCents)}
                </span>
              </div>
            </div>
          </>
        )}

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onCancel}>Cancelar (Esc)</button>
          <button className="btn btn-success" onClick={() => onConfirm(method, changeCents)} disabled={!canConfirm}>
            Confirmar (Enter)
          </button>
        </div>
      </div>
    </div>
  )
}
