export interface CadenaSugeridaDto {
  movimiento_id: string;
  arrendatario_id: string | null;
  arrendatario_nombre: string | null;
  propiedad_id: string | null;
  propiedad_nombre: string | null;
  factura_id: string | null;
  factura_folio: string | null;
  factura_saldo: number;
  monto_disponible: number;
  score: number;
  motivo: string[];
}

export interface SugerenciasCadenaDto {
  items: CadenaSugeridaDto[];
}

export interface MovimientoDisponibleDto {
  id: string;
  fecha: string | null;
  depositante_original: string | null;
  depositante_normalizado: string | null;
  monto: number;
  disponible: number;
}

export interface AplicacionPagoDto {
  id: string;
  movimiento_id: string;
  factura_id: string;
  monto_aplicado: number;
  metodo: string;
  activa: boolean;
  fecha_aplicacion: string;
  responsable: string | null;
  created_at: string;
}

export interface AplicacionesListDto {
  total: number;
  items: AplicacionPagoDto[];
}

export interface SaldosFacturaDto {
  factura_id: string;
  total: number;
  total_pagado: number;
  saldo_pendiente: number;
  estado_pago: string;
}

export interface SaldosMovimientoDto {
  movimiento_id: string;
  monto: number;
  total_aplicado: number;
  disponible: number;
  totalidad: string;
}

export interface AplicarCadenaPayload {
  movimiento_id: string;
  arrendatario_id: string;
  propiedad_id: string;
  factura_id: string;
  monto_aplicado: number;
}

export interface FacturaCandidataDto {
  factura_id: string;
  folio: string;
  saldo_pendiente: number;
  razon_social_receptor: string;
}

export interface ExcedenteDto {
  movimiento_id: string;
  monto_disponible: number;
  facturas_candidatas: FacturaCandidataDto[];
}

export interface CrearAplicacionResponse {
  ok: boolean;
  aplicacion_id: string;
  idempotente: boolean;
  excedente: ExcedenteDto | null;
}