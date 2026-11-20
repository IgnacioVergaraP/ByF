import { Injectable } from '@angular/core';
import { HttpClient, HttpEvent } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  FacturaDto, FacturaImportResultDto, FacturasListDto,
} from '../models/factura.model';

@Injectable({ providedIn: 'root' })
export class FacturaService {
  private readonly baseUrl = '/api/conciliacion';

  constructor(private http: HttpClient) {}

  importarLote(files: File[]): Observable<HttpEvent<FacturaImportResultDto>> {
    const formData = new FormData();
    files.forEach((f) => formData.append('files[]', f, f.name));
    return this.http.post<FacturaImportResultDto>(
      `${this.baseUrl}/facturas/import`, formData,
      { observe: 'events', reportProgress: true }
    );
  }

  getFacturas(): Observable<FacturasListDto> {
    return this.http.get<FacturasListDto>(`${this.baseUrl}/facturas`);
  }

  getFactura(id: string): Observable<FacturaDto> {
    return this.http.get<FacturaDto>(`${this.baseUrl}/facturas/${id}`);
  }
}