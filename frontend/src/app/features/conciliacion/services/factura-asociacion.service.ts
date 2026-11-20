import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  AsociacionesFacturaListDto,
  SugerenciasFacturaDto,
} from '../models/asociacion-factura.model';

export interface AsociarFacturaPayload {
  arrendatario_id: string;
  propiedades: Array<{ propiedad_id: string; conceptos: string[] }>;
  confirmar_identidad: boolean;
}

@Injectable({ providedIn: 'root' })
export class FacturaAsociacionService {
  private readonly baseUrl = '/api/conciliacion';

  constructor(private http: HttpClient) {}

  getSugerencias(facturaId: string): Observable<SugerenciasFacturaDto> {
    return this.http.get<SugerenciasFacturaDto>(
      `${this.baseUrl}/facturas/${facturaId}/sugerencias`
    );
  }

  getAsociaciones(facturaId: string): Observable<AsociacionesFacturaListDto> {
    return this.http.get<AsociacionesFacturaListDto>(
      `${this.baseUrl}/facturas/${facturaId}/asociaciones`
    );
  }

  asociar(facturaId: string, payload: AsociarFacturaPayload): Observable<any> {
    return this.http.post(
      `${this.baseUrl}/facturas/${facturaId}/asociar`, payload
    );
  }

  desasociar(facturaId: string): Observable<any> {
    return this.http.delete(`${this.baseUrl}/facturas/${facturaId}/asociar`);
  }

  confirmarIdentidad(
    rut_receptor: string, arrendatario_id: string, razon_social: string,
  ): Observable<any> {
    return this.http.post(`${this.baseUrl}/identidades-tributarias`, {
      rut_receptor, arrendatario_id, razon_social,
    });
  }
}