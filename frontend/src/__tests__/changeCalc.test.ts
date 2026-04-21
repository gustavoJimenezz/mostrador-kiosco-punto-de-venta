import { describe, it, expect } from 'vitest'
import { calculateChange, formatCents } from '../utils/changeCalc'

describe('calculateChange', () => {
  it('retorna 0 cuando el monto recibido es exactamente el total', () => {
    expect(calculateChange('100.00', '100.00')).toBe(0)
  })

  it('retorna vuelto positivo cuando el monto supera el total', () => {
    expect(calculateChange('87.50', '100.00')).toBe(1250)
  })

  it('retorna negativo cuando falta dinero', () => {
    expect(calculateChange('100.00', '50.00')).toBe(-5000)
  })

  it('evita errores de punto flotante con valores decimales críticos', () => {
    // 0.1 + 0.2 = 0.30000000000000004 con aritmética float directa
    expect(calculateChange('0.10', '0.30')).toBe(20)
  })

  it('trata el string vacío como monto recibido = 0', () => {
    expect(calculateChange('50.00', '')).toBe(-5000)
  })

  it('trata un string no numérico como monto recibido = 0', () => {
    expect(calculateChange('50.00', 'abc')).toBe(-5000)
  })

  it('maneja totales con muchos decimales (redondeo)', () => {
    expect(calculateChange('1.005', '2.00')).toBe(100)
  })

  it('retorna 0 para total y recibido ambos en 0', () => {
    expect(calculateChange('0.00', '0.00')).toBe(0)
  })
})

describe('formatCents', () => {
  it('formatea centavos positivos a string con 2 decimales', () => {
    expect(formatCents(1250)).toBe('12.50')
  })

  it('formatea centavos negativos usando valor absoluto', () => {
    expect(formatCents(-500)).toBe('5.00')
  })

  it('formatea cero', () => {
    expect(formatCents(0)).toBe('0.00')
  })

  it('formatea valores sin parte decimal exacta', () => {
    expect(formatCents(100)).toBe('1.00')
  })
})
