import {
  Component, ElementRef, EventEmitter, Input, OnChanges, OnDestroy, Output, SimpleChanges, ViewChild,
} from '@angular/core';
import { Subject, finalize, takeUntil } from 'rxjs';

import { ConciliacionPagoService } from '../../services/conciliacion-pago.service';
import {
  AplicacionPagoDto, CadenaSugeridaDto, ExcedenteDto,
  FacturaCandidataDto, MovimientoDisponibleDto, SaldosFacturaDto,
} from '../../models/aplicacion-pago.model';
import { FacturaDto } from '../../models/factura.model';

@Component({
  selector: 'app-factura-aplicaciones',
  templateUrl: './factura-aplicaciones.component.html',
  styleUrls: ['./factura-aplicaciones.component.scss'],
  standalone: false,
})
export class FacturaAplicacionesComponent implements OnChanges, OnDestroy {
  @Input() factura: FacturaDto | null = null;
  @Output() cerrar = new EventEmitter<void>();
  @Output() cambio = new EventEmitter<void>();

  loading = false;
  guardando = false;
  errorMessage: string | null = null;

  saldos: SaldosFacturaDto | null = null;
  aplicaciones: AplicacionPagoDto[] = [];
  sugerencias: CadenaSugeridaDto[] = [];

  verTodos = false;
  movimientosDisponibles: MovimientoDisponibleDto[] = [];
  movimientosFiltrados: MovimientoDisponibleDto[] = [];
  busquedaDepositante = '';
  movimientoSeleccionado: MovimientoDisponibleDto | null = null;
  montoManual: number | null = null;

  excedente: ExcedenteDto | null = null;

  @ViewChild('modalExcedente')
  set modalExcedente(elemento: ElementRef<HTMLDialogElement> | undefined) {
    if (elemento && !elemento.nativeElement.open) elemento.nativeElement.showModal();
  }

  private revisionExcedente = 0;
  private destroy$ = new Subject<void>();

  constructor(private pagoService: ConciliacionPagoService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['factura'] && this.factura) {
      this.revisionExcedente++;
      this.excedente = null;
      this.load();
      this.loadSugerencias();
      this.recuperarExcedente();
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  get sugerenciasParaMostrar(): CadenaSugeridaDto[] {
    return this.sugerencias.filter((s) => s.score >= 60);
  }

  load(): void {
    if (!this.factura) return;
    this.loading = true;
    this.pagoService.getSaldosFactura(this.factura.id)
      .pipe(takeUntil(this.destroy$))
      .subscribe((r) => (this.saldos = r));
    this.pagoService.getAplicacionesDeFactura(this.factura.id)
      .pipe(
        finalize(() => (this.loading = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => (this.aplicaciones = r.items.filter((a) => a.activa)),
        error: (err) => (this.errorMessage = `Error: ${err.message}`),
      });
  }

  loadSugerencias(): void {
    if (!this.factura) return;
    this.pagoService.getSugerenciasFactura(this.factura.id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (r) => (this.sugerencias = r.items),
        error: () => (this.sugerencias = []),
      });
  }

  private recuperarExcedente(): void {
    if (!this.factura) return;
    const revision = this.revisionExcedente;
    this.pagoService.getExcedentesFactura(this.factura.id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (r) => {
          if (revision === this.revisionExcedente) {
            this.excedente = r.items.find((e) => e.monto_disponible > 0) ?? null;
          }
        },
        error: (err) => (this.errorMessage = `No se pudo consultar el excedente: ${err.message}`),
      });
  }

  // ---------- Sugerencias ----------
  aplicarSugerencia(s: CadenaSugeridaDto): void {
    if (!this.factura || !s.movimiento_id || !s.arrendatario_id || !s.propiedad_id) return;
    const monto = Math.min(s.monto_disponible, s.factura_saldo);
    if (monto <= 0) return;

    this.guardando = true;
    this.errorMessage = null;
    this.pagoService.aplicarCadena({
      movimiento_id: s.movimiento_id,
      arrendatario_id: s.arrendatario_id,
      propiedad_id: s.propiedad_id,
      factura_id: this.factura.id,
      monto_aplicado: monto,
    })
      .pipe(
        finalize(() => (this.guardando = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.revisionExcedente++;
          this.excedente = r.excedente;
          this.load();
          this.loadSugerencias();
          if (this.verTodos) this.loadMovimientosDisponibles();
          this.cambio.emit();
        },
        error: (err) => (this.errorMessage = err.error?.error ?? err.message),
      });
  }

  // ---------- Selector manual ----------
  toggleVerTodos(): void {
    this.verTodos = !this.verTodos;
    if (this.verTodos && this.movimientosDisponibles.length === 0) {
      this.loadMovimientosDisponibles();
    }
  }

  loadMovimientosDisponibles(): void {
    this.pagoService.getMovimientosDisponibles()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (r) => {
          this.movimientosDisponibles = r.items;
          this.aplicarFiltroDepositante();
        },
        error: (err) => (this.errorMessage = `Error: ${err.message}`),
      });
  }

  aplicarFiltroDepositante(): void {
    const t = this.busquedaDepositante.trim().toLowerCase();
    if (!t) {
      this.movimientosFiltrados = this.movimientosDisponibles.slice(0, 20);
      return;
    }
    this.movimientosFiltrados = this.movimientosDisponibles
      .filter((m) => (m.depositante_original ?? '').toLowerCase().includes(t))
      .slice(0, 20);
  }

  seleccionarMovimiento(m: MovimientoDisponibleDto): void {
    this.movimientoSeleccionado = m;
    const saldo = this.saldos?.saldo_pendiente ?? this.factura?.saldo_pendiente ?? 0;
    this.montoManual = Math.min(m.disponible, saldo);
  }

  confirmarManual(): void {
    if (!this.factura || !this.movimientoSeleccionado || !this.montoManual) {
      this.errorMessage = 'Selecciona un depósito y un monto válido.';
      return;
    }
    if (this.montoManual <= 0) {
      this.errorMessage = 'El monto debe ser mayor a cero.';
      return;
    }
    const llave = `manual-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this.guardando = true;
    this.errorMessage = null;
    this.pagoService
      .crearAplicacion(this.movimientoSeleccionado.id, this.factura.id, this.montoManual, llave)
      .pipe(
        finalize(() => (this.guardando = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.revisionExcedente++;
          this.excedente = r.excedente;
          this.movimientoSeleccionado = null;
          this.montoManual = null;
          this.load();
          this.loadSugerencias();
          this.loadMovimientosDisponibles();
          this.cambio.emit();
        },
        error: (err) => (this.errorMessage = err.error?.error ?? err.message),
      });
  }

  // ---------- Excedente ----------
  aplicarExcedente(factura: FacturaCandidataDto): void {
    if (!this.excedente) return;
    const monto = Math.min(this.excedente.monto_disponible, factura.saldo_pendiente);
    if (monto <= 0) return;
    const llave = `exc-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    this.guardando = true;
    this.errorMessage = null;
    this.pagoService.crearAplicacion(
      this.excedente.movimiento_id, factura.factura_id, monto, llave
    )
      .pipe(
        finalize(() => (this.guardando = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.revisionExcedente++;
          this.excedente = r.excedente;
          this.load();
          this.loadSugerencias();
          if (this.verTodos) this.loadMovimientosDisponibles();
          this.cambio.emit();
        },
        error: (err) => (this.errorMessage = err.error?.error ?? err.message),
      });
  }

  ignorarExcedente(): void {
    this.revisionExcedente++;
    this.excedente = null;
  }

  // ---------- Revertir ----------
  revertir(a: AplicacionPagoDto): void {
    if (!confirm(`¿Revertir la aplicación de $${a.monto_aplicado.toLocaleString('es-CL')}?`)) return;
    this.guardando = true;
    this.pagoService.revertir(a.id)
      .pipe(
        finalize(() => (this.guardando = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: () => {
          this.revisionExcedente++;
          this.excedente = null;
          this.load();
          this.loadSugerencias();
          if (this.verTodos) this.loadMovimientosDisponibles();
          this.cambio.emit();
        },
        error: (err) => (this.errorMessage = err.error?.error ?? err.message),
      });
  }

  cancelar(): void { this.cerrar.emit(); }

  estadoClass(estado: string): string {
    if (estado === 'pagada') return 'ok';
    if (estado === 'parcial') return 'warn';
    if (estado === 'requiere_revision') return 'danger';
    return 'muted';
  }

  scoreClass(score: number): string {
    if (score >= 90) return 'ok';
    if (score >= 60) return 'warn';
    return 'muted';
  }
}