/**
 * Panel de administrador con navegación lateral.
 * Agrupa: Inventario, Historial de caja, Historial de ventas,
 * Editar stock, Inyectar stock, Importar.
 */

import InventoryView from './admin/InventoryView'
import CashHistoryView from './admin/CashHistoryView'
import SalesHistoryView from './admin/SalesHistoryView'
import StockEditView from './admin/StockEditView'
import StockInjectView from './admin/StockInjectView'
import ImportView from './admin/ImportView'

export type AdminSection =
  | 'inventory' | 'cash_history' | 'sales_history'
  | 'stock_edit' | 'stock_inject' | 'import'

interface NavItem { key: AdminSection; label: string; shortcut?: string }

const NAV_ITEMS: NavItem[] = [
  { key: 'inventory',      label: 'Inventario',         shortcut: 'F5' },
  { key: 'cash_history',   label: 'Historial de caja' },
  { key: 'sales_history',  label: 'Historial de ventas', shortcut: 'F2' },
  { key: 'stock_edit',     label: 'Editar stock',        shortcut: 'F6' },
  { key: 'stock_inject',   label: 'Inyectar stock',      shortcut: 'F7' },
  { key: 'import',         label: 'Importar',            shortcut: 'F9' },
]

interface Props {
  section: AdminSection
  onSectionChange: (s: AdminSection) => void
}

export default function AdminPanel({ section, onSectionChange }: Props) {
  return (
    <div className="admin-layout">
      {/* Sidebar */}
      <nav className="admin-sidebar">
        {NAV_ITEMS.map((item) => (
          <div
            key={item.key}
            className={`admin-sidebar-item ${section === item.key ? 'active' : ''}`}
            onClick={() => onSectionChange(item.key)}
          >
            {item.label}
            {item.shortcut && (
              <span className="tab-shortcut" style={{ float: 'right', marginLeft: 8 }}>{item.shortcut}</span>
            )}
          </div>
        ))}
      </nav>

      {/* Contenido */}
      <div className="admin-content">
        {section === 'inventory'     && <InventoryView />}
        {section === 'cash_history'  && <CashHistoryView />}
        {section === 'sales_history' && <SalesHistoryView />}
        {section === 'stock_edit'    && <StockEditView />}
        {section === 'stock_inject'  && <StockInjectView />}
        {section === 'import'        && <ImportView />}
      </div>
    </div>
  )
}
