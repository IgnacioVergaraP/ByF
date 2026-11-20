export interface CentroCostoRefDto {
  id: string;
  codigo: string;
  nombre_normalizado?: string;
}

export interface ArrendatarioRefDto {
  id: string;
  nombre_original: string;
  nombre_normalizado: string;
}

export type FacturaTotalidad = 'sin_aplicar' | 'aplicado_parcial' | 'aplicado_total';

export interface FacturaRelacionadaDto {
  folio: string;
  factura_id: string;
  monto_aplicado: number;
}

export interface MovimientoDto {
  id: string;
  fecha: string;
  descripcion_original: string;
  depositante_original: string | null;
  depositante_normalizado: string | null;
  monto: number;
  pagina_origen: number;
  orden_en_pagina: number;
  estado: string;
  cartola_id: string;
  centro_costo: { id: string; codigo: string } | null;
  centros_costo: CentroCostoRefDto[];
  arrendatarios: ArrendatarioRefDto[];
  total_aplicado: number;
  disponible: number;
  totalidad: FacturaTotalidad;
  facturas_relacionadas: FacturaRelacionadaDto[];
  factura_folio: string | null;
  factura_totalidad: FacturaTotalidad | null;
}

export interface CartolaImportResultDto {
  cartola_id: string;
  duplicada: boolean;
  cantidad_movimientos: number;
  total_abonos_extraido: number;
  total_abonos_informado: number | null;
  validacion_ok: boolean;
  validacion_mensaje: string | null;
}

export interface MovimientosListDto {
  total: number;
  total_abonos: number;
  pendientes: number;
  asociados: number;
  items: MovimientoDto[];
}