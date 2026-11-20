export interface DetalleFacturaDto {
  id: string;
  codigo: string | null;
  descripcion: string | null;
  cantidad: number | null;
  unidad: string | null;
  precio_unitario: number | null;
  descuento: number | null;
  total_linea: number | null;
}

export interface AsociacionFacturaRefDto {
  id: string;
  propiedad: { id: string; nombre_original: string } | null;
  centro_costo: { id: string; codigo: string } | null;
  conceptos: string[];
  estado: string;
  metodo: string;
}

export type EstadoPagoFactura = 'pendiente' | 'parcial' | 'pagada' | 'requiere_revision';

export interface FacturaDto {
  id: string;
  tipo_documento: string;
  folio: string;
  rut_emisor: string | null;
  razon_social_emisor: string | null;
  rut_receptor: string | null;
  razon_social_receptor: string | null;
  fecha_emision: string | null;
  fecha_vencimiento: string | null;
  neto: number | null;
  exento: number | null;
  iva: number | null;
  total: number | null;
  total_pagado: number;
  saldo_pendiente: number;
  estado_pago: EstadoPagoFactura;
  archivo_nombre: string;
  estado: string;
  estado_asociacion: string;
  validacion_ok: boolean;
  validacion_mensaje: string | null;
  created_at: string | null;
  detalles?: DetalleFacturaDto[];
  asociaciones?: AsociacionFacturaRefDto[];
}

export interface FacturasListDto {
  total: number;
  items: FacturaDto[];
}

export interface FacturaImportResultDto {
  importacion_id: string;
  archivos_recibidos: number;
  facturas_validas: number;
  facturas_duplicadas: number;
  facturas_con_error: number;
  detalles: Array<{
    archivo: string;
    ok: boolean;
    duplicada: boolean;
    folio: string | null;
    errores: string[];
  }>;
}