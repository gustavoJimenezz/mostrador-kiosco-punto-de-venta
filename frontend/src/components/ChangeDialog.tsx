/**
 * Diálogo de vuelto para pagos en efectivo (F12).
 * Muestra el total, permite ingresar el monto recibido y calcula el vuelto.
 */

import { useEffect, useRef, useState } from 'react'

interface Props {
  total: string
  onConfirm: () => void
  onCancel: () => void
}

export default function ChangeDialog({ total, onConfirm, onCancel }: Props) {
  const [received, setReceived] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
      if (e.key === 'Enter') {
        e.preventDefault()
        if (canConfirm) onConfirm()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [received])

  const totalCents = Math.round(parseFloat(total) * 100)
  const receivedNum = parseFloat(received) || 0
  const receivedCents = Math.round(receivedNum * 100)
  const changeCents = receivedCents - totalCents
  const canConfirm = receivedCents >= totalCents

  const fmt = (cents: number) => (Math.abs(cents) / 100).toFixed(2)

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 360 }}>
        <div className="modal-title">Cobrar en efectivo</div>

        <div className="groupbox" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>Total a cobrar</span>
            <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--success)' }}>${total}</span>
          </div>
        </div>

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

        {received !== '' && (
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
                ${fmt(changeCents)}
              </span>
            </div>
          </div>
        )}

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onCancel}>Cancelar (Esc)</button>
          <button className="btn btn-success" onClick={onConfirm} disabled={!canConfirm}>
            Confirmar (Enter)
          </button>
        </div>
      </div>
    </div>
  )
}
