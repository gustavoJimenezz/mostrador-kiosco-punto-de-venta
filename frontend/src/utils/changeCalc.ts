/**
 * Calcula el vuelto en centavos.
 * Retorna un valor negativo si el monto recibido no alcanza para cubrir el total.
 */
export function calculateChange(totalStr: string, receivedStr: string): number {
  const totalCents = Math.round(parseFloat(totalStr) * 100)
  const receivedCents = Math.round((parseFloat(receivedStr) || 0) * 100)
  return receivedCents - totalCents
}

/** Formatea centavos a string con 2 decimales (valor absoluto). */
export function formatCents(cents: number): string {
  return (Math.abs(cents) / 100).toFixed(2)
}
