/**
 * Estado global del carrito de compras (Zustand).
 *
 * El carrito vive en memoria del cliente solo para la UI.
 * Al confirmar la venta, se envía {items: [{product_id, qty}]} al servidor.
 * El servidor asigna price_at_sale desde la DB — el cliente nunca envía precios.
 */

import { create } from 'zustand'

export interface CartItem {
  product_id: number
  barcode: string
  name: string
  unit_price: string   // string para evitar float — viene del servidor como str
  qty: number
}

interface CartState {
  items: CartItem[]
  addItem: (product: Omit<CartItem, 'qty'>, qty?: number) => void
  removeItem: (product_id: number) => void
  updateQty: (product_id: number, qty: number) => void
  clear: () => void
  total: () => string
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],

  addItem: (product, qty = 1) => {
    set((state) => {
      const existing = state.items.find((i) => i.product_id === product.product_id)
      if (existing) {
        return {
          items: state.items.map((i) =>
            i.product_id === product.product_id
              ? { ...i, qty: i.qty + qty }
              : i,
          ),
        }
      }
      return { items: [...state.items, { ...product, qty }] }
    })
  },

  removeItem: (product_id) => {
    set((state) => ({
      items: state.items.filter((i) => i.product_id !== product_id),
    }))
  },

  updateQty: (product_id, qty) => {
    if (qty <= 0) {
      get().removeItem(product_id)
      return
    }
    set((state) => ({
      items: state.items.map((i) =>
        i.product_id === product_id ? { ...i, qty } : i,
      ),
    }))
  },

  clear: () => set({ items: [] }),

  /**
   * Calcula el total del carrito sumando unit_price * qty.
   * Usa enteros de centavos para evitar errores de punto flotante.
   * El total real se confirma server-side al procesar la venta.
   */
  total: () => {
    const items = get().items
    const totalCents = items.reduce((acc, item) => {
      const priceCents = Math.round(parseFloat(item.unit_price) * 100)
      return acc + priceCents * item.qty
    }, 0)
    return (totalCents / 100).toFixed(2)
  },
}))
