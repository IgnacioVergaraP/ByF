export interface PropiedadNodo {
  id: string;
  nombre_original: string;
  cc: string | null;
}

export interface ArrendatarioNodo {
  id: string;
  nombre_original: string;
  nombre_normalizado: string;
}

export interface DepositanteNodo {
  id: string;
  nombre_original: string;
  nombre_normalizado: string;
}

export interface AristaPA {
  propiedad_id: string;
  arrendatario_id: string;
  tipo: 'maestro';
}

export interface AristaAD {
  id: string;
  arrendatario_id: string;
  depositante_id: string;
  tipo: 'aprendida';
}

export interface GrafoDto {
  propiedades: PropiedadNodo[];
  arrendatarios: ArrendatarioNodo[];
  depositantes: DepositanteNodo[];
  aristas_propiedad_arrendatario: AristaPA[];
  aristas_arrendatario_depositante: AristaAD[];
}

export type VistaMapa = 'tarjetas' | 'tabla';

// Vistas procesadas para render
export interface DepositanteDeArrendatario {
  arista_id: string;
  depositante_id: string;
  nombre_original: string;
}

export interface ArrendatarioConRelaciones {
  arrendatario: ArrendatarioNodo;
  propiedades: Array<{ id: string; nombre_original: string; cc: string | null }>;
  depositantes: DepositanteDeArrendatario[];
}

export interface FilaTabla {
  arrendatario_id: string;
  arrendatario_nombre: string;
  propiedad_id: string | null;
  propiedad_nombre: string;
  cc: string | null;
  depositante_id: string | null;
  depositante_nombre: string;
  arista_id: string | null; // null si la fila es solo maestro sin depositante
}