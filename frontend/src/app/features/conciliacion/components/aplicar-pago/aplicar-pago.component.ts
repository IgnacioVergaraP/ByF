import {
  Component, EventEmitter, Input, OnChanges, OnDestroy, OnInit,
  Output, SimpleChanges,
} from '@angular/core';
import { Subject, finalize, takeUntil } from 'rxjs';

import { ConciliacionPagoService } from '../../services/conciliacion-pago.service';
import { FacturaService } from '../../services/factura.service';
import {
  CadenaSugeridaDto, ExcedenteDto, FacturaCandidataDto,
} from '../../models/aplicacion-pago.model';
import { MovimientoDto } from '../../models/cartola.model';
import { FacturaDto } from '../../models/factura.model';

@Component({
  selector: 'app-aplicar-pago',
  templateUrl: './aplicar-pago.component.html',
  styleUrls: ['./aplicar-pago.component.scss'],
  standalone: false,
})
export class AplicarPagoComponent implements OnInit, OnChanges, OnDestroy {
  @Input() movimiento: MovimientoDto | null = null;
  @Output() cerrar = new EventEmitter<void>();
  @Output() guardado = new EventEmitter<ExcedenteDto | null>();

  loading = false;
  guardando = false;
  errorMessage: string | null = null;

  sugerencias: CadenaSugeridaDto[] = [];
  facturasDisponibles: FacturaDto[] = [];

  modoManual = false;
  facturaManual: FacturaDto | null = null;
  montoManual: number | null = null;
  busquedaFactura = '';

  excedente: ExcedenteDto | null = null;

  private destroy$ = new Subject<void>();

  constructor(
    private pagoService: ConciliacionPagoService,
    private facturaService: FacturaService,
  ) {}

  ngOnInit(): void {
    this.loadFacturas();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['movimiento'] && this.movimiento) {
      this.loadSugerencias(this.movimiento.id);
      this.excedente = null;
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  get facturasFiltradas(): FacturaDto[] {
    const t = this.busquedaFactura.trim().toLowerCase();
    const base = this.facturasDisponibles.filter(
      (f) => f.estado_pago !== 'pagada' && (f.saldo_pendiente ?? 0) > 0
    );
    if (!t) return base.slice(0, 20);
    return base
      .filter((f) =>
        (f.folio ?? '').toLowerCase().includes(t) ||
        (f.razon_social_receptor ?? '').toLowerCase().includes(t)
      )
      .slice(0, 20);
  }

  loadSugerencias(movimientoId: string): void {
    this.loading = true;
    this.pagoService.getSugerenciasMovimiento(movimientoId)
      .pipe(
        finalize(() => (this.loading = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.sugerencias = r.items;
          if (this.sugerencias.length === 0) this.modoManual = true;
        },
        error: (err) => (this.errorMessage = `Error: ${err.message}`),
      });
  }

  loadFacturas(): void {
    this.facturaService.getFacturas()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (r) => (this.facturasDisponibles = r.items),
        error: () => (this.facturasDisponibles = []),
      });
  }

  aplicarSugerencia(c: CadenaSugeridaDto): void {
    if (!this.movimiento || !c.arrendatario_id || !c.propiedad_id || !c.factura_id) return;
    const monto = Math.min(c.monto_disponible, c.factura_saldo);
    if (monto <= 0) return;

    this.guardando = true;
    this.errorMessage = null;
    this.pagoService.aplicarCadena({
      movimiento_id: this.movimiento.id,
      arrendatario_id: c.arrendatario_id,
      propiedad_id: c.propiedad_id,
      factura_id: c.factura_id,
      monto_aplicado: monto,
    })
      .pipe(
        finalize(() => (this.guardando = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.onAplicacionGuardada(r.excedente);
        },
        error: (err) => (this.errorMessage = err.error?.error ?? err.message),
      });
  }

  seleccionarFactura(f: FacturaDto): void {
    this.facturaManual = f;
    const saldo = f.saldo_pendiente ?? (f.total ?? 0);
    const disponible = this.movimiento?.disponible ?? saldo;
    this.montoManual = Math.min(saldo, disponible);
  }

  confirmarManual(): void {
    if (!this.movimiento || !this.facturaManual || !this.montoManual) {
      this.errorMessage = 'Selecciona una factura y un monto válido.';
      return;
    }
    if (this.montoManual <= 0) {
      this.errorMessage = 'El monto debe ser mayor a cero.';
      return;
    }
    const llave = `manual-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this.guardando = true;
    this.errorMessage = null;
    this.pagoService.crearAplicacion(this.movimiento.id, this.facturaManual.id, this.montoManual, llave)
      .pipe(
        finalize(() => (this.guardando = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.onAplicacionGuardada(r.excedente);
        },
        error: (err) => (this.errorMessage = err.error?.error ?? err.message),
      });
  }

  aplicarExcedente(factura: FacturaCandidataDto): void {
    if (!this.excedente) return;
    const monto = Math.min(this.excedente.monto_disponible, factura.saldo_pendiente);
    if (monto <= 0) return;
    const llave = `exc-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this.guardando = true;
    this.pagoService.crearAplicacion(
      this.excedente.movimiento_id, factura.factura_id, monto, llave
    )
      .pipe(
        finalize(() => (this.guardando = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.onAplicacionGuardada(r.excedente);
        },
        error: (err) => (this.errorMessage = err.error?.error ?? err.message),
      });
  }

  private onAplicacionGuardada(excedente: ExcedenteDto | null): void {
    this.excedente = excedente;
    this.facturaManual = null;
    this.montoManual = null;
    this.errorMessage = null;

    if (excedente && excedente.monto_disponible > 0 && excedente.facturas_candidatas.length > 0) {
      if (this.movimiento) {
        this.movimiento = {
          ...this.movimiento,
          disponible: excedente.monto_disponible,
          total_aplicado: this.movimiento.monto - excedente.monto_disponible,
        };
      }
      // Renovar las opciones para no ofrecer facturas ya pagadas ni saldos anteriores.
      this.sugerencias = [];
      this.facturasDisponibles = [];
      this.loadSugerencias(excedente.movimiento_id);
      this.loadFacturas();
    }

    this.guardado.emit(excedente);
  }

  ignorarExcedente(): void { this.excedente = null; }

  cancelar(): void { this.cerrar.emit(); }

  scoreClass(score: number): string {
    if (score >= 90) return 'ok';
    if (score >= 60) return 'warn';
    return 'muted';
  }
}