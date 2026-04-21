/**
 * Pantalla principal del POS.
 *
 * Atajos de teclado:
 *   Enter    — buscar por código de barras (si solo dígitos) o por nombre
 *   ↑ / ↓   — navegar dropdown de búsqueda por nombre
 *   F4       — cobrar (efectivo)
 *   F12      — cobrar con diálogo de vuelto
 *   Supr     — quitar último ítem del carrito
 *   F1       — nueva venta (limpia carrito)
 *   F10      — cierre de caja (navega a caja)
 *   Esc      — cerrar dropdown / limpiar búsqueda
 */

import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useCartStore } from '../store/cartStore'
import ChangeDialog from '../components/ChangeDialog'
import { formatCents } from '../utils/changeCalc'

/** Parsea "N * término" → {qty, term}. Retorna null si no hay prefijo de cantidad. */
function parseQtyPrefix(raw: string): { qty: number; term: string } | null {
  const match = raw.match(/^(\d+)\s*\*\s*(.+)$/)
  if (!match) return null
  const qty = parseInt(match[1], 10)
  return qty > 0 ? { qty, term: match[2].trim() } : null
}

interface Props {
  cashCloseId: number | null
}

interface Product {
  id: number; barcode: string; name: string; current_price: string; stock: number
}
interface SaleResponse {
  id: string; total_amount: string; payment_method: string; timestamp: string; items: SaleItem[]
}
interface SaleItem {
  product_name: string; quantity: number; price_at_sale: string; subtotal: string
}
interface TodaySale {
  id: string; timestamp: string; total_amount: string; payment_method: string
  is_cancelled: boolean; cancelled_at: string | null; items: SaleItem[]
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const METHOD_LABELS: Record<string, string> = {
  EFECTIVO: 'Efectivo',
  DEBITO: 'Débito',
  TRANSFERENCIA: 'Transf.',
}

export default function POS({ cashCloseId }: Props) {
  const [input, setInput] = useState('')
  const [results, setResults] = useState<Product[]>([])
  const [highlighted, setHighlighted] = useState(-1)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [processing, setProcessing] = useState(false)
  const [showChange, setShowChange] = useState(false)
  const [todaySales, setTodaySales] = useState<TodaySale[]>([])
  const [expandedSaleId, setExpandedSaleId] = useState<string | null>(null)
  const [hoveredSaleId, setHoveredSaleId] = useState<string | null>(null)

  const { items, addItem, removeItem, updateQty, clear, total } = useCartStore()
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const refocusInput = () => {
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const loadTodaySales = async () => {
    try {
      const sales = await api.get<TodaySale[]>(`/sales?date=${todayStr()}`)
      setTodaySales(sales)
    } catch {
      // silencioso: la sección queda vacía
    }
  }

  useEffect(() => { loadTodaySales() }, [])

  // Búsqueda en tiempo real: 300ms después del último cambio en el input
  useEffect(() => {
    const raw = input.trim()
    const parsed = parseQtyPrefix(raw)
    const q = parsed?.term ?? raw

    // Mínimo 2 caracteres para evitar resultados masivos
    if (q.length < 2) return

    const timer = setTimeout(async () => {
      try {
        let found: Product[]
        if (/^\d+$/.test(q)) {
          found = await api.get<Product[]>(`/products/search-barcode?q=${encodeURIComponent(q)}`)
        } else {
          found = await api.get<Product[]>(`/products/search?q=${encodeURIComponent(q)}`)
        }
        setResults(found)
        setHighlighted(found.length > 0 ? 0 : -1)
      } catch {
        // silencioso: el usuario puede seguir escribiendo
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [input])

  // F4, F12, Supr — manejados en este componente
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'F4' || e.key === 'F12') {
        e.preventDefault()
        if (items.length > 0 && !processing) setShowChange(true)
      }
      if (e.key === 'Delete') {
        if (!input && items.length > 0) {
          e.preventDefault()
          removeItem(items[items.length - 1].product_id)
        }
      }
      if (e.key === 'Escape') {
        setResults([])
        setHighlighted(-1)
        setInput('')
        inputRef.current?.focus()
      }
      if (results.length > 0) {
        if (e.key === 'ArrowDown') {
          e.preventDefault()
          setHighlighted((h) => Math.min(h + 1, results.length - 1))
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault()
          setHighlighted((h) => Math.max(h - 1, -1))
        }
        if (e.key === 'Enter' && highlighted >= 0) {
          e.preventDefault()
          const parsed = parseQtyPrefix(input.trim())
          selectProduct(results[highlighted], parsed?.qty ?? 1)
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [items, input, results, highlighted, processing])

  const selectProduct = (p: Product, qty = 1) => {
    addItem({ product_id: p.id, barcode: p.barcode, name: p.name, unit_price: p.current_price }, qty)
    setResults([])
    setHighlighted(-1)
    setInput('')
    setMessage(null)
    refocusInput()
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    const raw = input.trim()
    if (!raw) return

    // Si hay dropdown abierto, seleccionar con la cantidad del prefijo si aplica
    if (results.length > 0) {
      const parsed = parseQtyPrefix(raw)
      const qty = parsed?.qty ?? 1
      const target = highlighted >= 0 ? results[highlighted] : results[0]
      selectProduct(target, qty)
      return
    }

    const parsed = parseQtyPrefix(raw)
    const qty = parsed?.qty ?? 1
    const q = parsed?.term ?? raw

    try {
      if (/^\d+$/.test(q)) {
        try {
          const product = await api.get<Product>(`/products/barcode/${q}`)
          selectProduct(product, qty)
        } catch {
          // Sin coincidencia exacta → buscar por coincidencia parcial de barcode
          const found = await api.get<Product[]>(`/products/search-barcode?q=${encodeURIComponent(q)}`)
          if (found.length === 0) {
            setMessage({ text: `No se encontró código "${q}"`, type: 'error' })
            setResults([])
            setInput('')
          } else if (found.length === 1) {
            selectProduct(found[0], qty)
          } else {
            setResults(found)
            setHighlighted(0)
          }
        }
      } else {
        const found = await api.get<Product[]>(`/products/search?q=${encodeURIComponent(q)}`)
        if (found.length === 0) {
          setMessage({ text: `No se encontró "${q}"`, type: 'error' })
          setResults([])
        } else if (found.length === 1) {
          selectProduct(found[0], qty)
        } else {
          setResults(found)
          setHighlighted(0)
        }
      }
    } catch {
      setMessage({ text: `Producto "${q}" no encontrado`, type: 'error' })
      setResults([])
      setInput('')
    }
  }

  const handleSale = async (paymentMethod: string, changeCents?: number) => {
    if (items.length === 0 || processing) return
    setProcessing(true)
    setShowChange(false)
    try {
      const sale = await api.post<SaleResponse>('/sales', {
        items: items.map((i) => ({ product_id: i.product_id, qty: i.qty })),
        payment_method: paymentMethod,
        cash_close_id: cashCloseId,
      })
      const changeStr = changeCents !== undefined && changeCents > 0
        ? ` | Vuelto: $${formatCents(changeCents)}`
        : ''
      setMessage({ text: `✓ Venta confirmada — Total: $${sale.total_amount}${changeStr}`, type: 'success' })
      setTodaySales((prev) => [...prev, sale])
      clear()
    } catch (err: unknown) {
      setMessage({ text: err instanceof Error ? err.message : 'Error al procesar la venta', type: 'error' })
    } finally {
      setProcessing(false)
      refocusInput()
    }
  }

  const handleNewSale = () => {
    clear()
    setMessage(null)
    refocusInput()
  }

  const handleDeleteItem = () => {
    if (items.length > 0) {
      removeItem(items[items.length - 1].product_id)
      refocusInput()
    }
  }

  const totalStr = total()
  const todayTotal = todaySales
    .filter(s => !s.is_cancelled)
    .reduce((acc, s) => acc + parseFloat(s.total_amount), 0)
    .toFixed(2)

  return (
    <div
      className="pos-wrapper"
      onMouseDown={(e) => {
        if (showChange) return
        if (e.target === inputRef.current) return
        e.preventDefault()
        inputRef.current?.focus()
      }}
    >
      <div className="pos-layout">
        {/* Panel izquierdo: búsqueda + carrito */}
        <div className="pos-main">
          {/* Barra de búsqueda */}
          <div className="search-wrapper">
            <form onSubmit={handleSearch} className="search-row">
              <span className="search-label">Código:</span>
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value)
                  setResults([])
                  setHighlighted(-1)
                  setMessage(null)
                }}
                placeholder="Escanear código o escribir nombre del producto y presionar Enter..."
                className="input input-lg"
                autoFocus
                autoComplete="off"
              />
            </form>
            <p className="search-hint">
              Ingresá: [Cantidad] * [Producto:Código/Nombre] para cargar varias unidades (ej: 3 * 7790001234)
            </p>

            {/* Dropdown de resultados */}
            {results.length > 0 && (
              <div className="search-dropdown" ref={dropdownRef}>
                {results.map((p, idx) => (
                  <div
                    key={p.id}
                    className={`search-dropdown-item ${idx === highlighted ? 'highlighted' : ''}`}
                    onMouseEnter={() => setHighlighted(idx)}
                    onClick={() => selectProduct(p)}
                  >
                    <span className="item-name">{p.name}</span>
                    <span className="item-barcode">{p.barcode}</span>
                    <span className="item-stock">Stock: {p.stock}</span>
                    <span className="item-price">${p.current_price}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Mensaje de estado */}
          {message && (
            <div className={`msg msg-${message.type}`}>{message.text}</div>
          )}

          {/* Tabla del carrito */}
          <div className="scroll-y card" style={{ padding: 0 }}>
            <table className="cart-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th className="td-center">Cant.</th>
                  <th className="td-right">Precio Unit.</th>
                  <th className="td-right">Subtotal</th>
                  <th style={{ width: 32 }}></th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-hint)', padding: '32px 0' }}>
                      Carrito vacío — escanee o busque un producto
                    </td>
                  </tr>
                )}
                {items.map((item) => {
                  const subtotalCents = Math.round(parseFloat(item.unit_price) * 100 * item.qty)
                  return (
                    <tr key={item.product_id}>
                      <td>{item.name}</td>
                      <td className="td-center">
                        <div className="cart-qty-controls">
                          <button
                            className="cart-qty-btn"
                            onClick={() => { updateQty(item.product_id, item.qty - 1); refocusInput() }}
                          >−</button>
                          <span style={{ minWidth: 24, textAlign: 'center', fontWeight: 600 }}>{item.qty}</span>
                          <button
                            className="cart-qty-btn"
                            onClick={() => { updateQty(item.product_id, item.qty + 1); refocusInput() }}
                          >+</button>
                        </div>
                      </td>
                      <td className="td-right font-mono">${item.unit_price}</td>
                      <td className="td-right font-mono font-bold">
                        ${(subtotalCents / 100).toFixed(2)}
                      </td>
                      <td>
                        <button
                          style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', fontSize: 16 }}
                          onClick={() => { removeItem(item.product_id); refocusInput() }}
                          title="Quitar"
                        >✕</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Panel derecho: total + ventas hoy + cobrar */}
        <div className="pos-sidebar">
          {/* Bloque total */}
          <div className="total-block">
            <div className="total-block-amount">TOTAL: ${totalStr}</div>
          </div>

          {/* Ventas de hoy */}
          <div className="ventas-hoy">
            <div className="ventas-hoy-header">
              <span>Ventas de hoy</span>
              <span className="font-mono font-bold">${todayTotal}</span>
            </div>
            <table className="ventas-hoy-table">
              <thead>
                <tr>
                  <th>Hora</th>
                  <th>Método</th>
                  <th className="td-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {todaySales.length === 0 && (
                  <tr>
                    <td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-hint)', padding: '8px 0', fontSize: 11 }}>
                      Sin ventas aún
                    </td>
                  </tr>
                )}
                {todaySales.map((s) => (
                  <React.Fragment key={s.id}>
                    <tr
                      style={{
                        cursor: 'pointer',
                        background: s.is_cancelled
                          ? 'var(--error-light, rgba(220,53,69,0.06))'
                          : hoveredSaleId === s.id ? 'var(--primary-light)' : undefined,
                        opacity: s.is_cancelled ? 0.65 : 1,
                        transition: 'background 0.15s',
                      }}
                      onClick={() => setExpandedSaleId(expandedSaleId === s.id ? null : s.id)}
                      onMouseEnter={() => setHoveredSaleId(s.id)}
                      onMouseLeave={() => setHoveredSaleId(null)}
                      title={s.is_cancelled ? 'Cancelada' : 'Click para ver detalle'}
                    >
                      <td className="font-mono" style={s.is_cancelled ? { textDecoration: 'line-through' } : {}}>{fmtTime(s.timestamp)}</td>
                      <td style={{ color: s.is_cancelled ? 'var(--error, #dc3545)' : undefined, fontSize: 11 }}>
                        {s.is_cancelled ? 'Cancelada' : (METHOD_LABELS[s.payment_method] ?? s.payment_method)}
                      </td>
                      <td className="td-right font-mono font-bold" style={s.is_cancelled ? { textDecoration: 'line-through', color: 'var(--text-hint)' } : {}}>${s.total_amount}</td>
                    </tr>
                    {expandedSaleId === s.id && s.items.length > 0 && (
                      <tr>
                        <td colSpan={3} style={{ padding: 0, background: 'var(--primary-light)', borderBottom: '1px solid var(--border)' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                            <tbody>
                              {s.items.map((item, i) => (
                                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                  <td style={{ padding: '3px 8px', color: 'var(--text-primary)' }}>{item.product_name}</td>
                                  <td style={{ padding: '3px 4px', textAlign: 'center', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>×{item.quantity}</td>
                                  <td style={{ padding: '3px 8px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: 'var(--primary)', whiteSpace: 'nowrap' }}>${item.subtotal}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>

          {/* Botón principal cobrar */}
          <button
            className="btn btn-success btn-lg btn-full cobrar-btn"
            onClick={() => { if (items.length > 0 && !processing) setShowChange(true) }}
            disabled={items.length === 0 || processing}
          >
            F4 - Cobrar
          </button>

          {/* Atajos pie de sidebar */}
          <div className="sidebar-footer-shortcuts">
            <button
              className="sidebar-shortcut-btn"
              onClick={handleNewSale}
            >
              F1 - Nueva Venta
            </button>
            <button
              className="sidebar-shortcut-btn"
              onClick={() => {/* F10 manejado en App.tsx */}}
            >
              F10 - Cierre Caja
            </button>
          </div>
        </div>
        
      </div>

      {/* Barra inferior de atajos */}
      <div className="pos-footer">
        <span>F1 borra todo el carrito · Supr borra el ítem seleccionado</span>
        <button
          className="btn btn-danger btn-sm"
          onClick={handleDeleteItem}
          disabled={items.length === 0}
        >
          Borrar ítem
        </button>
      </div>

      {/* Diálogo de vuelto */}
      {showChange && (
        <ChangeDialog
          total={totalStr}
          onConfirm={(paymentMethod, changeCents) => handleSale(paymentMethod, changeCents)}
          onCancel={() => { setShowChange(false); refocusInput() }}
        />
      )}
    </div>
  )
}
