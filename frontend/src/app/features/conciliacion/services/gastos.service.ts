import { Injectable } from '@angular/core';
import { HttpClient, HttpEvent, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  GastoEgresoDto,
  GastoArchivoDto,
  GastoListaDto,
  GastoDocumentoDto,
  GastosCatalogoDto,
} from '../models/gasto.model';

@Injectable({ providedIn: 'root' })
export class GastosService {
  private readonly baseUrl = '/api/conciliacion/gastos';

  constructor(private http: HttpClient) {}

  getCatalogo(): Observable<GastosCatalogoDto> {
    return this.http.get<GastosCatalogoDto>(`${this.baseUrl}/catalogo`);
  }

  getEgresos(centroCostoId?: string): Observable<GastoListaDto> {
    let params = new HttpParams();
    if (centroCostoId) params = params.set('centro_costo_id', centroCostoId);
    return this.http.get<GastoListaDto>(this.baseUrl, { params });
  }

  getDocumentos(centroCostoId?: string): Observable<{ total: number; items: GastoDocumentoDto[] }> {
    let params = new HttpParams();
    if (centroCostoId) params = params.set('centro_costo_id', centroCostoId);
    return this.http.get<{ total: number; items: GastoDocumentoDto[] }>(
      `${this.baseUrl}/documentos`, { params }
    );
  }

  getArchivos(centroCostoId?: string): Observable<{ cartolas: GastoArchivoDto[]; excels: GastoArchivoDto[] }> {
    let params = new HttpParams();
    if (centroCostoId) params = params.set('centro_costo_id', centroCostoId);
    return this.http.get<{ cartolas: GastoArchivoDto[]; excels: GastoArchivoDto[] }>(
      `${this.baseUrl}/archivos`, { params }
    );
  }

  eliminarArchivo(tipo: 'cartolas' | 'excels', id: string): Observable<{ ok: boolean }> {
    return this.http.delete<{ ok: boolean }>(`${this.baseUrl}/${tipo}/${id}`);
  }

  importarCartola(
    file: File,
    centroCostoId: string,
  ): Observable<HttpEvent<{
    duplicada: boolean;
    cantidad_cargos: number;
    cantidad_movimientos: number;
    validacion_mensaje: string | null;
  }>> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('centro_costo_id', centroCostoId);
    return this.http.post<{
      duplicada: boolean;
      cantidad_cargos: number;
      cantidad_movimientos: number;
      validacion_mensaje: string | null;
    }>(
      '/api/conciliacion/cartolas/import',
      formData,
      { observe: 'events', reportProgress: true }
    );
  }

  subirDocumento(
    file: File,
    centroCostoId: string,
  ): Observable<{ id: string; duplicada: boolean; cantidad_gastos: number; conciliados: number; pendientes_aprobacion: number; sin_coincidencia: number }> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('centro_costo_id', centroCostoId);
    return this.http.post<{ id: string; duplicada: boolean; cantidad_gastos: number; conciliados: number; pendientes_aprobacion: number; sin_coincidencia: number }>(
      `${this.baseUrl}/documentos`, formData
    );
  }

  clasificar(
    egreso: GastoEgresoDto,
    tipo: 'fijo' | 'variable',
    categoria: string | null,
    subcategoria: string | null,
    recordarRegla: boolean,
  ): Observable<GastoEgresoDto> {
    return this.http.put<GastoEgresoDto>(`${this.baseUrl}/${egreso.id}/clasificacion`, {
      tipo_gasto: tipo,
      categoria,
      subcategoria,
      recordar_regla: recordarRegla,
    });
  }

  desclasificar(egresoId: string): Observable<GastoEgresoDto> {
    return this.http.delete<GastoEgresoDto>(
      `${this.baseUrl}/${egresoId}/clasificacion`
    );
  }

  asociar(egresoId: string, documentoId: string, confirmar: boolean): Observable<{ id: string; estado: string }> {
    return this.http.post<{ id: string; estado: string }>(
      `${this.baseUrl}/${egresoId}/asociaciones`,
      { documento_id: documentoId, confirmar }
    );
  }

  desasociar(asociacionId: string): Observable<{ ok: boolean }> {
    return this.http.delete<{ ok: boolean }>(
      `${this.baseUrl}/asociaciones/${asociacionId}`
    );
  }

}
