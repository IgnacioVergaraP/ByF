export interface PropiedadCandidataDto {
  id: string;
  nombre_original: string;
  conceptos?: string[];
  centro_costo?: { id: string; codigo: string } | null;
}

export interface SugerenciaArrendatarioDto {
  arrendatario_id: string;
  nombre: string;
  score: number;
  propiedades: PropiedadCandidataDto[];
}

export interface SugerenciasFacturaDto {
  factura_id: string;
  rut_receptor: string | null;
  razon_social_receptor: string | null;
  codigos_detectados: string[];
  identidad_aprendida: {
    arrendatario: { id: string; nombre_original: string };
    propiedades: { id: string; nombre_original: string }[];
  } | null;
  sugerencias: SugerenciaArrendatarioDto[];
}

export interface AsociacionFacturaDto {
  id: string;
  factura_id: string;
  propiedad: { id: string; nombre_original: string } | null;
  centro_costo: { id: string; codigo: string } | null;
  conceptos: string[];
  estado: string;
  metodo: string;
}

export interface AsociacionesFacturaListDto {
  factura_id: string;
  estado_asociacion: string;
  items: AsociacionFacturaDto[];
}