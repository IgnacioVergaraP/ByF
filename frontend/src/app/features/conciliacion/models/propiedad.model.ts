export interface CentroCostoDto {
  id: string;
  codigo: string;
  nombre_original: string;
  nombre_normalizado: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ArrendatarioDto {
  id: string;
  nombre_original: string;
  nombre_normalizado: string;
}

export interface PropiedadDto {
  id: string;
  nombre_original: string;
  nombre_normalizado: string;
  centro_costo: CentroCostoDto | null;
  arrendatarios: ArrendatarioDto[];
  conceptos: string[];
}

export interface ListResponse<T> {
  total: number;
  items: T[];
}

export interface ImportResultDto {
  total_rows: number;
  imported_rows: number;
  skipped_rows: number;
  errors: { row: number; message: string }[];
}