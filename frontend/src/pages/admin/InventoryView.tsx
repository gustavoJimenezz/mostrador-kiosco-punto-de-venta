/**
 * Vista de gestión de productos (Inventario) — Admin (F5).
 * CRUD completo de productos con modal de edición.
 */

import { useEffect, useState } from 'react'
import { api } from '../../api/client'

interface Category { id: number; name: string }
interface Product {
  id: number; barcode: string; name: string
  current_cost: string; margin_percent: string; current_price: string
  stock: number; min_stock: number; category_id: number | null
}

interface FormData {
  barcode: string; name: string; current_cost: string
  margin_percent: string; stock: string; min_stock: string
  category_id: string
}

const emptyForm: FormData = {
  barcode: '', name: '', current_cost: '0.00',
  margin_percent: '30.00', stock: '0', min_stock: '0', category_id: '',
}

function calcPrice(cost: string, margin: string) {
  const c = parseFloat(cost) || 0
  const m = parseFloat(margin) || 0
  return (c * (1 + m / 100)).toFixed(2)
}

export default function InventoryView() {
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  // Modal
  const [modalOpen, setModalOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<FormData>(emptyForm)
  const [saving, setSaving] = useState(false)

  // Categorías modal
  const [newCatName, setNewCatName] = useState('')
  const [catMsg, setCatMsg] = useState('')

  const load = async () => {
    try {
      const [prods, cats] = await Promise.all([
        api.get<Product[]>('/products'),
        api.get<Category[]>('/categories'),
      ])
      setProducts(prods)
      setCategories(cats)
    } catch {
      setMsg({ text: 'Error al cargar datos', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMsg({ text, type })
    setTimeout(() => setMsg(null), 3000)
  }

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyForm)
    setModalOpen(true)
  }

  const openEdit = (p: Product) => {
    setEditingId(p.id)
    setForm({
      barcode: p.barcode, name: p.name,
      current_cost: p.current_cost, margin_percent: p.margin_percent,
      stock: String(p.stock), min_stock: String(p.min_stock),
      category_id: p.category_id ? String(p.category_id) : '',
    })
    setModalOpen(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    const body = {
      barcode: form.barcode, name: form.name,
      current_cost: form.current_cost, margin_percent: form.margin_percent,
      stock: parseInt(form.stock), min_stock: parseInt(form.min_stock),
      category_id: form.category_id ? parseInt(form.category_id) : null,
    }
    try {
      if (editingId) {
        await api.put(`/products/${editingId}`, body)
        showMsg('Producto actualizado', 'success')
      } else {
        await api.post('/products', body)
        showMsg('Producto creado', 'success')
      }
      setModalOpen(false)
      await load()
    } catch (err: unknown) {
      showMsg(err instanceof Error ? err.message : 'Error al guardar', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`¿Eliminar "${name}"?`)) return
    try {
      await api.delete(`/products/${id}`)
      setProducts((prev) => prev.filter((p) => p.id !== id))
      showMsg('Producto eliminado', 'success')
    } catch (err: unknown) {
      showMsg(err instanceof Error ? err.message : 'Error al eliminar', 'error')
    }
  }

  const handleCreateCat = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const cat = await api.post<Category>('/categories', { name: newCatName })
      setCategories((prev) => [...prev, cat])
      setNewCatName('')
      setCatMsg('Categoría creada')
      setTimeout(() => setCatMsg(''), 2000)
    } catch (err: unknown) {
      setCatMsg(err instanceof Error ? err.message : 'Error')
    }
  }

  const filtered = products.filter((p) =>
    !filter || p.name.toLowerCase().includes(filter.toLowerCase()) || p.barcode.includes(filter)
  )

  const setField = (k: keyof FormData, v: string) => setForm((f) => ({ ...f, [k]: v }))

  if (loading) return <div style={{ padding: 32, color: 'var(--text-secondary)' }}>Cargando...</div>

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {msg && <div className={`msg msg-${msg.type}`}>{msg.text}</div>}

      <div className="admin-content-header">
        <span className="admin-content-title">Inventario de Productos</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input" placeholder="Buscar por nombre o código…"
            value={filter} onChange={(e) => setFilter(e.target.value)}
            style={{ width: 260 }}
          />
          <button className="btn btn-primary" onClick={openCreate}>+ Nuevo producto</button>
        </div>
      </div>

      {/* Categorías rápidas */}
      <div className="groupbox" style={{ paddingBottom: 10 }}>
        <div className="groupbox-title" style={{ marginBottom: 8 }}>Categorías</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {categories.map((c) => (
            <span key={c.id} className="badge badge-info">{c.name}</span>
          ))}
          <form onSubmit={handleCreateCat} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input
              className="input" placeholder="Nueva categoría…"
              value={newCatName} onChange={(e) => setNewCatName(e.target.value)}
              style={{ width: 180 }}
              required
            />
            <button type="submit" className="btn btn-secondary btn-sm">Agregar</button>
            {catMsg && <span style={{ fontSize: 12, color: 'var(--success)' }}>{catMsg}</span>}
          </form>
        </div>
      </div>

      {/* Tabla de productos */}
      <div className="scroll-y card" style={{ padding: 0, flex: 1 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Código</th>
              <th>Nombre</th>
              <th>Categoría</th>
              <th className="td-right">Costo</th>
              <th className="td-right">Margen</th>
              <th className="td-right">Precio</th>
              <th className="td-center">Stock</th>
              <th className="td-center">Mín.</th>
              <th style={{ width: 80 }}></th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={9} className="td-center" style={{ padding: '24px 0', color: 'var(--text-hint)' }}>Sin resultados</td></tr>
            )}
            {filtered.map((p) => {
              const cat = categories.find((c) => c.id === p.category_id)
              return (
                <tr key={p.id}>
                  <td className="td-mono text-secondary">{p.barcode}</td>
                  <td style={{ fontWeight: 500 }}>{p.name}</td>
                  <td>{cat ? <span className="badge badge-info">{cat.name}</span> : <span className="text-secondary">—</span>}</td>
                  <td className="td-right td-mono">${p.current_cost}</td>
                  <td className="td-right text-secondary">{p.margin_percent}%</td>
                  <td className="td-right td-mono font-bold" style={{ color: 'var(--primary)' }}>${p.current_price}</td>
                  <td className={`td-center font-bold ${p.stock <= p.min_stock ? 'text-danger' : 'text-success'}`}>{p.stock}</td>
                  <td className="td-center text-secondary">{p.min_stock}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => openEdit(p)}>Editar</button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(p.id, p.name)}>✕</button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="text-secondary" style={{ fontSize: 12 }}>{filtered.length} producto{filtered.length !== 1 ? 's' : ''}</div>

      {/* Modal crear/editar */}
      {modalOpen && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">{editingId ? 'Editar producto' : 'Nuevo producto'}</div>
            <form onSubmit={handleSave}>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Código de barras</label>
                  <input className="input" value={form.barcode} onChange={(e) => setField('barcode', e.target.value)} required />
                </div>
                <div className="form-group" style={{ flex: 2 }}>
                  <label className="form-label">Nombre</label>
                  <input className="input" value={form.name} onChange={(e) => setField('name', e.target.value)} required />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Costo ($)</label>
                  <input type="number" min="0" step="0.01" className="input" value={form.current_cost} onChange={(e) => setField('current_cost', e.target.value)} required />
                </div>
                <div className="form-group">
                  <label className="form-label">Margen (%)</label>
                  <input type="number" min="0" step="0.01" className="input" value={form.margin_percent} onChange={(e) => setField('margin_percent', e.target.value)} required />
                </div>
                <div className="form-group">
                  <label className="form-label">Precio calculado</label>
                  <input className="input" value={`$${calcPrice(form.current_cost, form.margin_percent)}`} readOnly style={{ background: 'var(--primary-light)', color: 'var(--primary)', fontWeight: 700 }} />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Stock inicial</label>
                  <input type="number" min="0" className="input" value={form.stock} onChange={(e) => setField('stock', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Stock mínimo</label>
                  <input type="number" min="0" className="input" value={form.min_stock} onChange={(e) => setField('min_stock', e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Categoría</label>
                  <select className="input" value={form.category_id} onChange={(e) => setField('category_id', e.target.value)}>
                    <option value="">Sin categoría</option>
                    {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setModalOpen(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
