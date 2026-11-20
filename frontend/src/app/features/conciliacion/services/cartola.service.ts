import { Injectable } from '@angular/core';
import { HttpClient, HttpEvent } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  CartolaImportResultDto,
  CentroCostoRefDto,
  MovimientosListDto,
} from '../models/cartola.model';

export interface CentrosCostoEnMovimientosDto {
  total: number;
  items: CentroCostoRefDto[];
}

@Injectable({ providedIn: 'root' })
export class CartolaService {
  private readonly baseUrl = '/api/conciliacion';

  constructor(private http: HttpClient) {}

  importCartola(
    file: File,
    centroCostoId: string,
  ): Observable<HttpEvent<CartolaImportResultDto>> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('centro_costo_id', centroCostoId);
    return this.http.post<CartolaImportResultDto>(
      `${this.baseUrl}/cartolas/import`,
      formData,
      { observe: 'events', reportProgress: true }
    );
  }

  getMovimientos(): Observable<MovimientosListDto> {
    return this.http.get<MovimientosListDto>(`${this.baseUrl}/movimientos`);
  }

  getCentrosCostoEnMovimientos(): Observable<CentrosCostoEnMovimientosDto> {
    return this.http.get<CentrosCostoEnMovimientosDto>(
      `${this.baseUrl}/centros-costo-en-movimientos`
    );
  }
}