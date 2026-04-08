/**
 * Vista Calendario — historial mensual de ventas + notas editables por día.
 *
 * Cada celda es editable: el usuario puede escribir notas que se guardan
 * automáticamente en localStorage (clave: "pos_calendar_notes").
 * Los totales de ventas se obtienen de GET /api/cash/history.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

interface CashClose {
  id: number
  opened_at: string
  closed_at: string | null
  is_open: boolean
  opening_amount: string
  total_sales: string
  total_sales_cash: string
  total_sales_debit: string
  total_sales_transfer: string
}

type DayMap   = Record<string, CashClose>
type NotesMap = Record<string, string>      // "YYYY-MM-DD" → texto libre

const STORAGE_KEY = 'pos_calendar_notes'
const MONTHS_ES   = [
  'Enero','Febrero','Marzo','Abril','Mayo','Junio',
  'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre',
]
const DAYS_ES = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']
const CELL_LINES = 6

function dowArg(date: Date)                         { return (date.getDay() + 6) % 7 }
function isoDate(y: number, m: number, d: number)   { return `${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}` }
function todayISO()                                 { const t = new Date(); return isoDate(t.getFullYear(), t.getMonth(), t.getDate()) }
function fmt$(v: string)                            { return parseFloat(v).toLocaleString('es-AR', { minimumFractionDigits: 2 }) }

function loadNotes(): NotesMap {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') } catch { return {} }
}
function saveNotes(notes: NotesMap) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(notes))
}

// ── Celda individual ──────────────────────────────────────────────────────────
interface DayCellProps {
  day: number
  dateKey: string
  isToday: boolean
  cc?: CashClose
  note: string
  onNoteChange: (key: string, val: string) => void
}

function DayCell({ day, dateKey, isToday, cc, note, onNoteChange }: DayCellProps) {
  const taRef = useRef<HTMLTextAreaElement>(null)

  return (
    <div className={`cal-cell${isToday ? ' cal-cell-today-col' : ''}`}>
      {/* Número del día */}
      <div className="cal-day-number">
        {isToday
          ? <span className="cal-today-badge">{day}</span>
          : <span>{day}</span>
        }
      </div>

      {/* Resumen de ventas — solo si hay ventas */}
      {cc && parseFloat(cc.total_sales) > 0 && (
        <div className="cal-day-data">
          <div className="cal-day-total">${fmt$(cc.total_sales)}</div>
          {parseFloat(cc.total_sales_cash)     > 0 && <div className="cal-day-line cal-line-cash">Ef: ${fmt$(cc.total_sales_cash)}</div>}
          {parseFloat(cc.total_sales_debit)    > 0 && <div className="cal-day-line cal-line-debit">Déb: ${fmt$(cc.total_sales_debit)}</div>}
          {parseFloat(cc.total_sales_transfer) > 0 && <div className="cal-day-line cal-line-transfer">Transf: ${fmt$(cc.total_sales_transfer)}</div>}
        </div>
      )}

      {/* Líneas decorativas de fondo */}
      <div className="cal-lines" aria-hidden="true">
        {Array.from({ length: CELL_LINES }).map((_, i) => <div key={i} className="cal-line-rule" />)}
      </div>

      {/* Textarea editable superpuesto sobre las líneas */}
      <textarea
        ref={taRef}
        className="cal-note-input"
        value={note}
        onChange={(e) => onNoteChange(dateKey, e.target.value)}
        spellCheck={false}
        aria-label={`Nota del día ${day}`}
      />
    </div>
  )
}

// ── Componente principal ───────────────────────────────────────────────────────
export default function CalendarView() {
  const today = new Date()
  const [year,  setYear]  = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [dayMap, setDayMap] = useState<DayMap>({})
  const [notes,  setNotes]  = useState<NotesMap>(loadNotes)
  const [loading, setLoading] = useState(false)

  // Grilla del mes
  const firstDay    = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const startOffset = dowArg(firstDay)

  const cells: (number | null)[] = [
    ...Array(startOffset).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]
  while (cells.length % 7 !== 0) cells.push(null)

  // Cargar historial del mes
  useEffect(() => {
    setLoading(true)
    const start = isoDate(year, month, 1)
    const end   = isoDate(year, month, daysInMonth)
    api.get<CashClose[]>(`/cash/history?start=${start}&end=${end}`)
      .then((closes) => {
        const map: DayMap = {}
        for (const cc of closes) { map[cc.opened_at.slice(0, 10)] = cc }
        setDayMap(map)
      })
      .catch(() => setDayMap({}))
      .finally(() => setLoading(false))
  }, [year, month])

  const prevMonth = () => { if (month === 0) { setYear(y => y-1); setMonth(11) } else setMonth(m => m-1) }
  const nextMonth = () => { if (month === 11) { setYear(y => y+1); setMonth(0)  } else setMonth(m => m+1) }

  // Actualizar nota y persistir en localStorage
  const handleNoteChange = useCallback((key: string, val: string) => {
    setNotes(prev => {
      const updated = { ...prev, [key]: val }
      saveNotes(updated)
      return updated
    })
  }, [])

  const todayKey = todayISO()
  const weeks    = cells.length / 7

  return (
    <div className="cal-wrapper">
      {/* Navegación de mes */}
      <div className="cal-header">
        <button className="cal-nav-btn" onClick={prevMonth} aria-label="Mes anterior">◄</button>
        <div className="cal-title">
          {MONTHS_ES[month]}  {year}
          {loading && <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-hint)', marginLeft: 10 }}>cargando…</span>}
        </div>
        <button className="cal-nav-btn" onClick={nextMonth} aria-label="Mes siguiente">►</button>
      </div>

      {/* Grilla */}
      <div className="cal-grid" style={{ gridTemplateRows: `32px repeat(${weeks}, 1fr)` }}>
        {/* Cabeceras */}
        {DAYS_ES.map(d => (
          <div key={d} className="cal-day-header">{d}</div>
        ))}

        {/* Celdas */}
        {cells.map((day, idx) => {
          if (day === null) return <div key={`e-${idx}`} className="cal-cell cal-cell-empty" />
          const key = isoDate(year, month, day)
          return (
            <DayCell
              key={key}
              day={day}
              dateKey={key}
              isToday={key === todayKey}
              cc={dayMap[key]}
              note={notes[key] ?? ''}
              onNoteChange={handleNoteChange}
            />
          )
        })}
      </div>
    </div>
  )
}
