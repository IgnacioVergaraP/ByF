import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  ArrendatarioConRelaciones,
  AristaAD,
  FilaTabla,
  GrafoDto,
} from '../models/grafo.model';

@Injectable({ providedIn: 'root' })
export class GrafoApiService {
  private readonly baseUrl = '/api/conciliacion';

  constructor(private http: HttpClient) {}

  getGrafo(): Observable<GrafoDto> {
    return this.http.get<GrafoDto>(`${this.baseUrl}/grafo`);
  }

  // ---------- Transformaciones de datos para las vistas ----------

  /** Construye la lista de arrendatarios con sus propiedades y depositantes. */
  construirTarjetas(grafo: GrafoDto): ArrendatarioConRelaciones[] {
    const propsPorArr = new Map<string, Array<{ id: string; nombre_original: string; cc: string | null }>>();
    for (const a of grafo.aristas_propiedad_arrendatario) {
      const prop = grafo.propiedades.find((p) => p.id === a.propiedad_id);
      if (!prop) continue;
      if (!propsPorArr.has(a.arrendatario_id)) propsPorArr.set(a.arrendatario_id, []);
      propsPorArr.get(a.arrendatario_id)!.push({
        id: prop.id,
        nombre_original: prop.nombre_original,
        cc: prop.cc,
      });
    }

    const depsPorArr = new Map<string, AristaAD[]>();
    for (const a of grafo.aristas_arrendatario_depositante) {
      if (!depsPorArr.has(a.arrendatario_id)) depsPorArr.set(a.arrendatario_id, []);
      depsPorArr.get(a.arrendatario_id)!.push(a);
    }

    const out: ArrendatarioConRelaciones[] = [];
    for (const arr of grafo.arrendatarios) {
      const props = propsPorArr.get(arr.id) ?? [];
      const deps = (depsPorArr.get(arr.id) ?? []).map((a) => {
        const dep = grafo.depositantes.find((d) => d.id === a.depositante_id);
        return {
          arista_id: a.id,
          depositante_id: a.depositante_id,
          nombre_original: dep?.nombre_original ?? a.depositante_id,
        };
      });
      out.push({ arrendatario: arr, propiedades: props, depositantes: deps });
    }

    out.sort((x, y) => x.arrendatario.nombre_original.toLowerCase().localeCompare(
      y.arrendatario.nombre_original.toLowerCase()
    ));
    return out;
  }

  /** Construye filas planas: una por cada (arrendatario, propiedad, depositante). */
  construirTabla(grafo: GrafoDto): FilaTabla[] {
    const filas: FilaTabla[] = [];
    const depsPorArr = new Map<string, AristaAD[]>();
    for (const a of grafo.aristas_arrendatario_depositante) {
      if (!depsPorArr.has(a.arrendatario_id)) depsPorArr.set(a.arrendatario_id, []);
      depsPorArr.get(a.arrendatario_id)!.push(a);
    }

    // Agrupar propiedades por arrendatario
    const propsPorArr = new Map<string, Array<{ id: string; nombre_original: string; cc: string | null }>>();
    for (const a of grafo.aristas_propiedad_arrendatario) {
      const prop = grafo.propiedades.find((p) => p.id === a.propiedad_id);
      if (!prop) continue;
      if (!propsPorArr.has(a.arrendatario_id)) propsPorArr.set(a.arrendatario_id, []);
      propsPorArr.get(a.arrendatario_id)!.push({
        id: prop.id,
        nombre_original: prop.nombre_original,
        cc: prop.cc,
      });
    }

    for (const arr of grafo.arrendatarios) {
      const props = propsPorArr.get(arr.id) ?? [];
      const deps = depsPorArr.get(arr.id) ?? [];

      if (props.length === 0 && deps.length === 0) {
        filas.push({
          arrendatario_id: arr.id,
          arrendatario_nombre: arr.nombre_original,
          propiedad_id: null,
          propiedad_nombre: '—',
          cc: null,
          depositante_id: null,
          depositante_nombre: '—',
          arista_id: null,
        });
        continue;
      }

      if (deps.length === 0) {
        for (const p of props) {
          filas.push({
            arrendatario_id: arr.id,
            arrendatario_nombre: arr.nombre_original,
            propiedad_id: p.id,
            propiedad_nombre: p.nombre_original,
            cc: p.cc,
            depositante_id: null,
            depositante_nombre: '(sin depositante)',
            arista_id: null,
          });
        }
        continue;
      }

      // Producto cartesiano propiedad × depositante, pero si no hay props, solo deps
      if (props.length === 0) {
        for (const d of deps) {
          const dep = grafo.depositantes.find((x) => x.id === d.depositante_id);
          filas.push({
            arrendatario_id: arr.id,
            arrendatario_nombre: arr.nombre_original,
            propiedad_id: null,
            propiedad_nombre: '—',
            cc: null,
            depositante_id: d.depositante_id,
            depositante_nombre: dep?.nombre_original ?? d.depositante_id,
            arista_id: d.id,
          });
        }
        continue;
      }

      for (const p of props) {
        for (const d of deps) {
          const dep = grafo.depositantes.find((x) => x.id === d.depositante_id);
          filas.push({
            arrendatario_id: arr.id,
            arrendatario_nombre: arr.nombre_original,
            propiedad_id: p.id,
            propiedad_nombre: p.nombre_original,
            cc: p.cc,
            depositante_id: d.depositante_id,
            depositante_nombre: dep?.nombre_original ?? d.depositante_id,
            arista_id: d.id,
          });
        }
      }
    }

    return filas;
  }
}