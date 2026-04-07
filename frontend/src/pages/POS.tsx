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

import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useCartStore } from '../store/cartStore'
import ChangeDialog from '../components/ChangeDialog'

interface Product {
  id: number; barcode: string; name: string; current_price: string; stock: number
}
interface SaleResponse {
  id: string; total_amount: string; payment_method: string; timestamp: string
}
interface TodaySale {
  id: string; timestamp: string; total_amount: string; payment_method: string
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

export default function POS() {
  const [input, setInput] = useState('')
  const [results, setResults] = useState<Product[]>([])
  const [highlighted, setHighlighted] = useState(-1)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [processing, setProcessing] = useState(false)
  const [showChange, setShowChange] = useState(false)
  const [todaySales, setTodaySales] = useState<TodaySale[]>([])

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

  // F4, F12, Supr — manejados en este componente
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'F4') {
        e.preventDefault()
        handleSale('EFECTIVO')
      }
      if (e.key === 'F12') {
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
          selectProduct(results[highlighted])
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [items, input, results, highlighted, processing])

  const selectProduct = (p: Product) => {
    addItem({ product_id: p.id, barcode: p.barcode, name: p.name, unit_price: p.current_price })
    setResults([])
    setHighlighted(-1)
    setInput('')
    setMessage(null)
    refocusInput()
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = input.trim()
    if (!q) return

    if (results.length > 0 && highlighted >= 0) {
      selectProduct(results[highlighted])
      return
    }
    if (results.length > 0) {
      selectProduct(results[0])
      return
    }

    try {
      if (/^\d+$/.test(q)) {
        const product = await api.get<Product>(`/products/barcode/${q}`)
        selectProduct(product)
      } else {
        const found = await api.get<Product[]>(`/products/search?q=${encodeURIComponent(q)}`)
        if (found.length === 0) {
          setMessage({ text: `No se encontró "${q}"`, type: 'error' })
          setResults([])
        } else if (found.length === 1) {
          selectProduct(found[0])
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

  const handleSale = async (paymentMethod: string) => {
    if (items.length === 0 || processing) return
    setProcessing(true)
    setShowChange(false)
    try {
      const sale = await api.post<SaleResponse>('/sales', {
        items: items.map((i) => ({ product_id: i.product_id, qty: i.qty })),
        payment_method: paymentMethod,
      })
      setMessage({ text: `✓ Venta confirmada — Total: $${sale.total_amount}`, type: 'success' })
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
    .reduce((acc, s) => acc + parseFloat(s.total_amount), 0)
    .toFixed(2)

  return (
    <div className="pos-wrapper">
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
                  <tr key={s.id}>
                    <td className="font-mono">{fmtTime(s.timestamp)}</td>
                    <td>{METHOD_LABELS[s.payment_method] ?? s.payment_method}</td>
                    <td className="td-right font-mono font-bold">${s.total_amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Botón principal cobrar */}
          <button
            className="btn btn-success btn-lg btn-full cobrar-btn"
            onClick={() => handleSale('EFECTIVO')}
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
          onConfirm={() => handleSale('EFECTIVO')}
          onCancel={() => { setShowChange(false); refocusInput() }}
        />
      )}
    </div>
  )
}
