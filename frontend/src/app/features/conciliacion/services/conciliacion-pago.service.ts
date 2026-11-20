import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  AplicacionesListDto,
  AplicarCadenaPayload,
  CrearAplicacionResponse,
  ExcedenteDto,
  MovimientoDisponibleDto,
  SaldosFacturaDto,
  SaldosMovimientoDto,
  SugerenciasCadenaDto,
} from '../models/aplicacion-pago.model';

export interface MovimientosDisponiblesDto {
  total: number;
  items: MovimientoDisponibleDto[];
}

@Injectable({ providedIn: 'root' })
export class ConciliacionPagoService {
  private readonly baseUrl = '/api/conciliacion';

  constructor(private http: HttpClient) {}

  getSugerenciasMovimiento(movimientoId: string): Observable<SugerenciasCadenaDto> {
    return this.http.get<SugerenciasCadenaDto>(
      `${this.baseUrl}/movimientos/${movimientoId}/sugerencias-facturas`
    );
  }

  getSugerenciasFactura(facturaId: string): Observable<SugerenciasCadenaDto> {
    return this.http.get<SugerenciasCadenaDto>(
      `${this.baseUrl}/facturas/${facturaId}/sugerencias-movimientos`
    );
  }

  getMovimientosDisponibles(): Observable<MovimientosDisponiblesDto> {
    return this.http.get<MovimientosDisponiblesDto>(
      `${this.baseUrl}/movimientos-disponibles`
    );
  }

  aplicarCadena(payload: AplicarCadenaPayload): Observable<CrearAplicacionResponse> {
    return this.http.post<CrearAplicacionResponse>(
      `${this.baseUrl}/conciliacion/aplicar-cadena`, payload
    );
  }

  crearAplicacion(
    movimientoId: string, facturaId: string, monto: number,
    llaveIdempotencia?: string,
  ): Observable<CrearAplicacionResponse> {
    return this.http.post<CrearAplicacionResponse>(
      `${this.baseUrl}/aplicaciones-pago`,
      {
        movimiento_id: movimientoId,
        factura_id: facturaId,
        monto_aplicado: monto,
        llave_idempotencia: llaveIdempotencia,
      }
    );
  }

  revertir(aplicacionId: string): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(
      `${this.baseUrl}/aplicaciones-pago/${aplicacionId}/revertir`,
      {}
    );
  }

  getAplicacionesDeFactura(facturaId: string): Observable<AplicacionesListDto> {
    return this.http.get<AplicacionesListDto>(
      `${this.baseUrl}/aplicaciones-pago?factura_id=${facturaId}`
    );
  }

  getAplicacionesDeMovimiento(movimientoId: string): Observable<AplicacionesListDto> {
    return this.http.get<AplicacionesListDto>(
      `${this.baseUrl}/aplicaciones-pago?movimiento_id=${movimientoId}`
    );
  }

  getExcedentesFactura(facturaId: string): Observable<{ items: ExcedenteDto[] }> {
    return this.http.get<{ items: ExcedenteDto[] }>(
      `${this.baseUrl}/facturas/${facturaId}/excedentes`
    );
  }

  getSaldosFactura(facturaId: string): Observable<SaldosFacturaDto> {
    return this.http.get<SaldosFacturaDto>(
      `${this.baseUrl}/facturas/${facturaId}/saldos`
    );
  }

  getSaldosMovimiento(movimientoId: string): Observable<SaldosMovimientoDto> {
    return this.http.get<SaldosMovimientoDto>(
      `${this.baseUrl}/movimientos/${movimientoId}/saldos`
    );
  }
}