/**
 * Vista de importación masiva de precios (F9).
 *
 * Flujo en 3 pasos:
 *   1. idle     — selección de archivo + descripción del formato
 *   2. mapping  — mapeo de columnas del archivo → campos destino + margen global
 *   3. importing — progreso y resultado de la importación
 */

import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'

const PREVIEW_ROWS = 100

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

type Step = 'idle' | 'mapping' | 'importing'

interface PreviewData {
  columns: string[]
  preview: Record<string, string>[]
  total_rows: number
}

interface ImportStatus {
  state: 'idle' | 'running' | 'done' | 'error'
  inserted: number
  updated: number
  skipped: number
  error_count: number
  error_message: string | null
}

// Campos destino del sistema
const DEST_FIELDS = [
  { key: 'barcode',  label: 'barcode *',  required: true  },
  { key: 'name',     label: 'name *',     required: true  },
  { key: 'net_cost', label: 'net_cost *', required: true  },
  { key: 'category', label: 'category',   required: false },
] as const

type DestKey = typeof DEST_FIELDS[number]['key']
type Mapping = Record<DestKey, string>

const UNASSIGNED = '(sin asignar)'

const EMPTY_MAPPING: Mapping = {
  barcode:  UNASSIGNED,
  name:     UNASSIGNED,
  net_cost: UNASSIGNED,
  category: UNASSIGNED,
}

// ---------------------------------------------------------------------------
// Colores de estado
// ---------------------------------------------------------------------------

const STATE_COLOR: Record<string, string> = {
  idle:    'var(--text-secondary)',
  running: 'var(--warning-amber)',
  done:    'var(--success)',
  error:   'var(--danger)',
}
const STATE_LABEL: Record<string, string> = {
  idle:    'Sin importaciones recientes',
  running: '⟳ Importando…',
  done:    '✓ Completado',
  error:   '✗ Error',
}

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

export default function ImportView() {
  const [step, setStep]             = useState<Step>('idle')
  const [file, setFile]             = useState<File | null>(null)
  const [preview, setPreview]       = useState<PreviewData | null>(null)
  const [mapping, setMapping]       = useState<Mapping>(EMPTY_MAPPING)
  const [useGlobalMargin, setUseGlobalMargin] = useState(true)
  const [globalMargin, setGlobalMargin]       = useState('30')
  const [loadingPreview, setLoadingPreview]   = useState(false)
  const [importStatus, setImportStatus]       = useState<ImportStatus | null>(null)
  const [msg, setMsg]               = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const fileRef  = useRef<HTMLInputElement>(null)
  const pollRef  = useRef<ReturnType<typeof setInterval> | null>(null)

  // Limpiar polling al desmontar
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  // --------------------------------------------------------------------------
  // Paso 1 → 2: cargar preview al seleccionar archivo
  // --------------------------------------------------------------------------

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null
    setFile(selected)
    setPreview(null)
    setMapping(EMPTY_MAPPING)
    setMsg(null)

    if (!selected) return

    setLoadingPreview(true)
    try {
      const data = await api.upload<PreviewData>('/import/preview', selected)
      setPreview(data)

      // Auto-mapeo: si el nombre de columna del archivo coincide exactamente
      // con un campo destino, pre-seleccionar.
      const autoMapping: Mapping = { ...EMPTY_MAPPING }
      const aliases: Record<string, DestKey> = {
        barcode: 'barcode', codigo: 'barcode', ean: 'barcode',
        name: 'name', nombre: 'name', descripcion: 'name',
        net_cost: 'net_cost', cost_price: 'net_cost', costo: 'net_cost', precio: 'net_cost',
        category: 'category', categoria: 'category',
      }
      for (const col of data.columns) {
        const dest = aliases[col.toLowerCase().trim()]
        if (dest && autoMapping[dest] === UNASSIGNED) {
          autoMapping[dest] = col
        }
      }
      setMapping(autoMapping)
      setStep('mapping')
    } catch (err: unknown) {
      setMsg({
        text: err instanceof Error ? err.message : 'Error al leer el archivo',
        type: 'error',
      })
    } finally {
      setLoadingPreview(false)
    }
  }

  // --------------------------------------------------------------------------
  // Paso 2 → 3: importar
  // --------------------------------------------------------------------------

  const canImport = DEST_FIELDS
    .filter(f => f.required)
    .every(f => mapping[f.key] !== UNASSIGNED)

  const handleImport = async () => {
    if (!file || !canImport) return
    setMsg(null)
    setStep('importing')

    // Construir mapping sin campos sin asignar
    const cleanMapping: Record<string, string> = {}
    for (const { key } of DEST_FIELDS) {
      if (mapping[key] !== UNASSIGNED) {
        cleanMapping[key] = mapping[key]
      }
    }

    const formData: Record<string, string> = {
      column_mapping: JSON.stringify(cleanMapping),
    }
    if (useGlobalMargin && globalMargin.trim()) {
      formData.global_margin = globalMargin.trim()
    }

    try {
      await api.uploadWithData('/import', file, formData)
      // Polling hasta que termine
      const poll = async () => {
        const s = await api.get<ImportStatus>('/import/status')
        setImportStatus(s)
        if (s.state !== 'running') clearInterval(pollRef.current!)
      }
      await poll()
      pollRef.current = setInterval(poll, 2000)
    } catch (err: unknown) {
      setMsg({
        text: err instanceof Error ? err.message : 'Error al importar',
        type: 'error',
      })
      setStep('mapping')
    }
  }

  // --------------------------------------------------------------------------
  // Volver a idle
  // --------------------------------------------------------------------------

  const handleReset = () => {
    setStep('idle')
    setFile(null)
    setPreview(null)
    setMapping(EMPTY_MAPPING)
    setMsg(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div style={{ maxWidth: 1100, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="admin-content-title">Importar lista de precios</div>

      {msg && <div className={`msg msg-${msg.type}`}>{msg.text}</div>}

      {/* ── PASO 1: selección de archivo ── */}
      {(step === 'idle' || step === 'mapping') && (
        <div className="groupbox">
          <div className="groupbox-title">Seleccionar archivo</div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="input"
              style={{ flex: 1 }}
              onChange={handleFileChange}
              disabled={loadingPreview}
            />
            {loadingPreview && (
              <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                Cargando vista previa…
              </span>
            )}
          </div>

          {file && !loadingPreview && preview && (
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
              <strong>{file.name}</strong> — {preview.total_rows} filas,{' '}
              {preview.columns.length} columnas
            </div>
          )}
        </div>
      )}

      {/* ── PASO 2: mapeo de columnas ── */}
      {step === 'mapping' && preview && (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16, alignItems: 'start' }}>

          {/* Panel izquierdo: mapping + margen */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="groupbox">
              <div className="groupbox-title">Mapeo de columnas</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
                Campos Destino — Columnas del archivo
              </div>

              {DEST_FIELDS.map(({ key, label, required }) => (
                <div className="form-group" key={key} style={{ marginBottom: 10 }}>
                  <label className="form-label" style={{ fontSize: 12 }}>
                    {label}
                  </label>
                  <select
                    className="input"
                    style={{ fontSize: 13 }}
                    value={mapping[key]}
                    onChange={e =>
                      setMapping(prev => ({ ...prev, [key]: e.target.value }))
                    }
                  >
                    <option value={UNASSIGNED}>
                      {required ? '— seleccionar —' : '(sin asignar)'}
                    </option>
                    {preview.columns.map(col => (
                      <option key={col} value={col}>{col}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>

            <div className="groupbox">
              <div className="groupbox-title">Margen de ganancia</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <input
                  type="checkbox"
                  id="use-margin"
                  checked={useGlobalMargin}
                  onChange={e => setUseGlobalMargin(e.target.checked)}
                />
                <label htmlFor="use-margin" style={{ fontSize: 13, cursor: 'pointer' }}>
                  Aplicar margen global al importar
                </label>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="number"
                  className="input"
                  style={{ width: 90, fontSize: 13 }}
                  value={globalMargin}
                  min="0"
                  max="999"
                  step="0.5"
                  disabled={!useGlobalMargin}
                  onChange={e => setGlobalMargin(e.target.value)}
                />
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>%</span>
              </div>
              {!useGlobalMargin && (
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>
                  Se usará el margen de cada fila del archivo, o 30% por defecto.
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-primary"
                onClick={handleImport}
                disabled={!canImport}
                title={!canImport ? 'Mapeá los campos requeridos (*) para continuar' : ''}
              >
                Importar
              </button>
              <button className="btn btn-secondary" onClick={handleReset}>
                Cancelar
              </button>
            </div>

            {!canImport && (
              <div style={{ fontSize: 11, color: 'var(--warning-amber)' }}>
                Mapeá los campos marcados con * para habilitar la importación.
              </div>
            )}
          </div>

          {/* Panel derecho: preview de filas */}
          <div className="groupbox" style={{ overflow: 'hidden' }}>
            <div className="groupbox-title">
              Vista previa del archivo{' '}
              <span style={{ fontWeight: 400, color: 'var(--text-secondary)' }}>
                (primeras {Math.min(preview.preview.length, PREVIEW_ROWS)} de{' '}
                {preview.total_rows} filas)
              </span>
            </div>
            <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 400 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr>
                    {preview.columns.map(col => (
                      <th
                        key={col}
                        style={{
                          padding: '6px 10px',
                          textAlign: 'left',
                          background: 'var(--surface-2)',
                          borderBottom: '1px solid var(--border)',
                          whiteSpace: 'nowrap',
                          color: 'var(--text-secondary)',
                          fontSize: 11,
                          textTransform: 'uppercase',
                        }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview.map((row, i) => (
                    <tr
                      key={i}
                      style={{ background: i % 2 === 0 ? 'transparent' : 'var(--surface-1)' }}
                    >
                      {preview.columns.map(col => (
                        <td
                          key={col}
                          style={{
                            padding: '5px 10px',
                            borderBottom: '1px solid var(--border)',
                            whiteSpace: 'nowrap',
                            maxWidth: 180,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {row[col] ?? ''}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── PASO 3: progreso / resultado ── */}
      {step === 'importing' && (
        <div className="groupbox">
          <div className="groupbox-title">Estado de la importación</div>

          {!importStatus || importStatus.state === 'running' ? (
            <div style={{ color: 'var(--warning-amber)', fontWeight: 600 }}>
              ⟳ Importando, por favor esperá…
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <span
                  style={{
                    fontWeight: 700,
                    color: STATE_COLOR[importStatus.state] ?? 'var(--text-primary)',
                    fontSize: 15,
                  }}
                >
                  {STATE_LABEL[importStatus.state] ?? importStatus.state}
                </span>
              </div>

              {importStatus.state === 'done' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
                  {[
                    { label: 'Insertados', val: importStatus.inserted, color: 'var(--success)' },
                    { label: 'Actualizados', val: importStatus.updated, color: 'var(--primary)' },
                    { label: 'Omitidos', val: importStatus.skipped, color: 'var(--text-secondary)' },
                  ].map(({ label, val, color }) => (
                    <div key={label} className="card" style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                        {label}
                      </div>
                      <div style={{ fontSize: 28, fontWeight: 800, color }}>{val}</div>
                    </div>
                  ))}
                </div>
              )}

              {importStatus.error_count > 0 && (
                <div className="msg msg-warning">
                  {importStatus.error_count} fila{importStatus.error_count !== 1 ? 's' : ''} con errores de parseo.
                </div>
              )}

              {importStatus.state === 'error' && importStatus.error_message && (
                <div className="msg msg-error">{importStatus.error_message}</div>
              )}

              <button className="btn btn-secondary" style={{ marginTop: 16 }} onClick={handleReset}>
                Nueva importación
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

