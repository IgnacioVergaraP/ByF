import { Injectable } from '@angular/core';
import { HttpClient, HttpEvent } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  ArrendatarioDto,
  CentroCostoDto,
  ImportResultDto,
  ListResponse,
  PropiedadDto,
} from '../models/propiedad.model';

@Injectable({ providedIn: 'root' })
export class ConciliacionService {
  private readonly baseUrl = '/api/conciliacion';

  constructor(private http: HttpClient) {}

  getPropiedades(): Observable<ListResponse<PropiedadDto>> {
    return this.http.get<ListResponse<PropiedadDto>>(`${this.baseUrl}/propiedades`);
  }

  getArrendatarios(): Observable<ListResponse<ArrendatarioDto>> {
    return this.http.get<ListResponse<ArrendatarioDto>>(`${this.baseUrl}/arrendatarios`);
  }

  getCentrosCosto(): Observable<ListResponse<CentroCostoDto>> {
    return this.http.get<ListResponse<CentroCostoDto>>(`${this.baseUrl}/centros-costo`);
  }

  importMaestro(file: File): Observable<HttpEvent<ImportResultDto>> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<ImportResultDto>(
      `${this.baseUrl}/maestro/import`,
      formData,
      { observe: 'events', reportProgress: true }
    );
  }
}