export interface GastosCatalogoDto {
  categorias: Record<string, string[]>;
}

export interface GastoDocumentoDto {
  id: string;
  centro_costo_id: string;
  archivo_nombre: string;
  destinatario?: string;
  observacion?: string;
  hoja?: string;
  fila?: number;
  fecha_documento: string | null;
  monto: number | null;
  estado: 'pagado' | 'pendiente_pago';
  asociaciones: {
    id: string;
    egreso_id: string;
    estado: 'sugerida' | 'confirmada';
  }[];
}

export interface GastoClasificacionDto {
  tipo_gasto: 'fijo' | 'variable';
  categoria: string | null;
  subcategoria: string | null;
  regla: {
    id: string;
    campo: string;
    valor: string;
    tipo_gasto: string;
    categoria: string | null;
    subcategoria: string | null;
  } | null;
}

export interface GastoEgresoDto {
  id: string;
  cartola_id: string;
  centro_costo_id: string;
  fecha: string;
  descripcion_original: string;
  beneficiario: string | null;
  monto: number;
  tipo_gasto: 'fijo' | 'variable' | null;
  categoria: string | null;
  subcategoria: string | null;
  clasificacion_origen: 'manual' | 'automatica' | null;
  regla: GastoClasificacionDto['regla'];
  sugerencia: GastoClasificacionDto | null;
  documentos: {
    id: string;
    asociacion_id: string;
    archivo_nombre: string;
    destinatario?: string;
    observacion?: string;
    hoja?: string;
    fila?: number;
    monto: number | null;
    fecha_documento: string | null;
    estado_asociacion: 'sugerida' | 'confirmada';
  }[];
  estado_conciliacion: 'conciliado' | 'sin_documento' | 'sugerido';
}

export interface GastoListaDto {
  total: number;
  items: GastoEgresoDto[];
}

export interface GastoArchivoDto {
  id: string;
  archivo_nombre: string;
  centro_costo_id: string;
  cantidad: number;
}

export type TipoArchivoGastos = 'cartolas' | 'excels' | 'documentos';
