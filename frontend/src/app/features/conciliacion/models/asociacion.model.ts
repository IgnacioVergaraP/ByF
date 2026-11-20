export interface ArrendatarioInfoDto {
  id: string;
  nombre_original: string;
  nombre_normalizado: string;
}

export interface PropiedadInfoDto {
  id: string;
  nombre_original: string;
}

export interface SugerenciasDto {
  movimiento_id: string;
  depositante_original: string | null;
  depositante_normalizado: string;
  monto: number;
  fecha: string;
  coincidencia_exacta: {
    arrendatario: ArrendatarioInfoDto | null;
    propiedades: PropiedadInfoDto[];
  } | null;
  sugerencias: Array<{
    arrendatario: ArrendatarioInfoDto | null;
    propiedades: PropiedadInfoDto[];
  }>;
}

export interface AsociacionItemDto {
  id: string;
  movimiento_id: string;
  asociacion_id: string;
  propiedad: PropiedadInfoDto | null;
  conceptos: string[];
  estado: string;
}

export interface AsociacionesMovimientoDto {
  movimiento_id: string;
  estado: string;
  items: AsociacionItemDto[];
}

export interface AsociarPayload {
  arrendatario_id: string;
  propiedades: Array<{ propiedad_id: string; conceptos: string[] }>;
}