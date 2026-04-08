/**
 * Vista de importación masiva de precios (F9).
 * Permite subir un CSV o Excel y monitorear el progreso.
 */

import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'

interface ImportStatus {
  state: 'idle' | 'running' | 'done' | 'error'
  inserted: number; updated: number; skipped: number
  error_count: number; error_message: string | null
}

export default function ImportView() {
  const [status, setStatus] = useState<ImportStatus | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadStatus = async () => {
    try {
      const s = await api.get<ImportStatus>('/import/status')
      setStatus(s)
      if (s.state !== 'running') {
        if (pollRef.current) clearInterval(pollRef.current)
      }
    } catch { /* silent */ }
  }

  useEffect(() => {
    loadStatus()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return
    setUploading(true)
    setMsg(null)
    try {
      await api.upload('/import', file)
      setMsg({ text: 'Importación iniciada. Revisá el estado más abajo.', type: 'success' })
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      // Polling cada 2 segundos mientras corre
      pollRef.current = setInterval(loadStatus, 2000)
      await loadStatus()
    } catch (err: unknown) {
      setMsg({ text: err instanceof Error ? err.message : 'Error al subir archivo', type: 'error' })
    } finally {
      setUploading(false)
    }
  }

  const stateColor: Record<string, string> = {
    idle: 'var(--text-secondary)',
    running: 'var(--warning-amber)',
    done: 'var(--success)',
    error: 'var(--danger)',
  }
  const stateLabel: Record<string, string> = {
    idle: 'Sin importaciones recientes',
    running: '⟳ Importando…',
    done: '✓ Completado',
    error: '✗ Error',
  }

  return (
    <div style={{ maxWidth: 720, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="admin-content-title">Importar lista de precios</div>

      {msg && <div className={`msg msg-${msg.type}`}>{msg.text}</div>}

      {/* Info del formato */}
      <div className="groupbox" style={{ background: 'var(--info-surface)', borderColor: 'var(--info-border)' }}>
        <div className="groupbox-title" style={{ color: 'var(--info-text)' }}>Formato del archivo (CSV / XLSX / XLS)</div>
        <div style={{ fontSize: 13, color: 'var(--info-text)', lineHeight: 1.6 }}>
          <p>El archivo debe contener las siguientes columnas <strong>(en cualquier orden)</strong>:</p>
          <ul style={{ marginLeft: 20, marginTop: 6 }}>
            <li><code>codigo</code> — Código de barras EAN-13 (requerido)</li>
            <li><code>nombre</code> — Nombre del producto (requerido)</li>
            <li><code>costo</code> — Costo sin IVA en ARS (requerido)</li>
            <li><code>margen</code> — Margen porcentual (opcional, default 30%)</li>
            <li><code>categoria</code> — Nombre de la categoría (opcional)</li>
          </ul>
          <p style={{ marginTop: 6 }}>
            Los productos existentes (mismo código) se <strong>actualizan</strong>.
            Los nuevos se <strong>insertan</strong>. El proceso corre en background sin bloquear el sistema.
          </p>
        </div>
      </div>

      {/* Formulario de carga */}
      <div className="groupbox">
        <div className="groupbox-title">Seleccionar archivo</div>
        <form onSubmit={handleUpload}>
          <div className="form-group">
            <label className="form-label">Archivo CSV, XLSX o XLS</label>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="input"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
          </div>
          {file && (
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
              Seleccionado: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
            </div>
          )}
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!file || uploading || status?.state === 'running'}
          >
            {uploading ? 'Subiendo…' : 'Iniciar importación'}
          </button>
          {status?.state === 'running' && (
            <span className="text-secondary" style={{ marginLeft: 12, fontSize: 13 }}>
              Esperá a que termine la importación actual.
            </span>
          )}
        </form>
      </div>

      {/* Estado */}
      {status && (
        <div className="groupbox">
          <div className="groupbox-title">Estado de la importación</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ fontWeight: 700, color: stateColor[status.state] ?? 'var(--text-primary)', fontSize: 15 }}>
              {stateLabel[status.state] ?? status.state}
            </span>
            {status.state === 'running' && (
              <button className="btn btn-secondary btn-sm" onClick={loadStatus}>↻ Actualizar</button>
            )}
          </div>

          {(status.state === 'done' || status.state === 'running') && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {[
                { label: 'Insertados', val: status.inserted, color: 'var(--success)' },
                { label: 'Actualizados', val: status.updated, color: 'var(--primary)' },
                { label: 'Omitidos', val: status.skipped, color: 'var(--text-secondary)' },
              ].map(({ label, val, color }) => (
                <div key={label} className="card" style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{label}</div>
                  <div style={{ fontSize: 24, fontWeight: 800, color }}>{val}</div>
                </div>
              ))}
            </div>
          )}

          {status.error_count > 0 && (
            <div className="msg msg-warning" style={{ marginTop: 12 }}>
              {status.error_count} fila{status.error_count !== 1 ? 's' : ''} con errores de parseo (formato incorrecto o campos faltantes).
            </div>
          )}

          {status.state === 'error' && status.error_message && (
            <div className="msg msg-error" style={{ marginTop: 12 }}>
              {status.error_message}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
