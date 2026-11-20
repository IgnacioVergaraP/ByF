import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  AsociacionesMovimientoDto,
  AsociarPayload,
  SugerenciasDto,
} from '../models/asociacion.model';

@Injectable({ providedIn: 'root' })
export class AsociacionApiService {
  private readonly baseUrl = '/api/conciliacion';

  constructor(private http: HttpClient) {}

  getSugerencias(movimientoId: string): Observable<SugerenciasDto> {
    return this.http.get<SugerenciasDto>(
      `${this.baseUrl}/movimientos/${movimientoId}/sugerencias`
    );
  }

  getAsociaciones(movimientoId: string): Observable<AsociacionesMovimientoDto> {
    return this.http.get<AsociacionesMovimientoDto>(
      `${this.baseUrl}/movimientos/${movimientoId}/asociaciones`
    );
  }

  asociar(movimientoId: string, payload: AsociarPayload): Observable<any> {
    return this.http.post(
      `${this.baseUrl}/movimientos/${movimientoId}/asociar`, payload
    );
  }

  corregir(movimientoId: string, payload: AsociarPayload): Observable<any> {
    return this.http.post(
      `${this.baseUrl}/movimientos/${movimientoId}/corregir`, payload
    );
  }

  desasociar(movimientoId: string): Observable<any> {
    return this.http.delete(
      `${this.baseUrl}/movimientos/${movimientoId}/asociar`
    );
  }

  crearAsociacionDirecta(
    arrendatarioId: string,
    depositanteNormalizado: string,
    depositanteOriginal?: string,
  ): Observable<any> {
    return this.http.post(`${this.baseUrl}/mapa/asociar`, {
      arrendatario_id: arrendatarioId,
      depositante_normalizado: depositanteNormalizado,
      depositante_original: depositanteOriginal,
    });
  }

  eliminarAsociacionDirecta(asociacionId: string): Observable<any> {
    return this.http.delete(`${this.baseUrl}/mapa/asociar/${asociacionId}`);
  }
}