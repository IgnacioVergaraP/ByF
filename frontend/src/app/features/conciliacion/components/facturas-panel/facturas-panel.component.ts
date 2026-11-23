import { Component, EventEmitter, OnDestroy, OnInit, Output } from '@angular/core';
import { Subject, Subscription, finalize, takeUntil } from 'rxjs';

import { FacturaService } from '../../services/factura.service';
import { EstadoPagoFactura, FacturaDto } from '../../models/factura.model';

@Component({
  selector: 'app-facturas-panel',
  templateUrl: './facturas-panel.component.html',
  styleUrls: ['./facturas-panel.component.scss'],
  standalone: false,
})
export class FacturasPanelComponent implements OnInit, OnDestroy {
  @Output() countChange = new EventEmitter<number>();

  errorMessage: string | null = null;

  facturas: FacturaDto[] = [];
  facturasFiltradas: FacturaDto[] = [];
  busqueda = '';
  periodoEmision = '';
  filtroPago: '' | EstadoPagoFactura = '';
  filtroAsociacion = '';
  paginaFacturas = 1;
  readonly facturasPorPagina = 15;
  cargando = false;

  facturaDetalle: FacturaDto | null = null;
  facturaAsociar: FacturaDto | null = null;
  facturaAplicaciones: FacturaDto | null = null;

  private destroy$ = new Subject<void>();
  private cargaActual?: Subscription;

  constructor(private service: FacturaService) {}

  ngOnInit(): void { this.cargar(); }
  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  cargar(): void {
    this.cargaActual?.unsubscribe();
    this.cargando = true;
    this.cargaActual = this.service.getFacturas()
      .pipe(
        finalize(() => (this.cargando = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.facturas = r.items;
          this.countChange.emit(this.facturas.length);
          this.aplicarFiltro(this.paginaFacturas);
        },
        error: (err) => (this.errorMessage = `Error: ${err.message}`),
      });
  }

  aplicarFiltro(pagina = 1): void {
    const t = this.busqueda.trim().toLowerCase();
    this.facturasFiltradas = this.facturas.filter((f) => {
      const coincideBusqueda = !t
        || (f.folio ?? '').toLowerCase().includes(t)
        || (f.razon_social_receptor ?? '').toLowerCase().includes(t)
        || (f.rut_receptor ?? '').toLowerCase().includes(t);
      return coincideBusqueda
        && (!this.periodoEmision || f.fecha_emision?.startsWith(this.periodoEmision))
        && (!this.filtroPago || f.estado_pago === this.filtroPago)
        && (!this.filtroAsociacion || f.estado_asociacion === this.filtroAsociacion);
    });
    const ultimaPagina = Math.max(1, Math.ceil(this.facturasFiltradas.length / this.facturasPorPagina));
    this.paginaFacturas = Math.min(pagina, ultimaPagina);
  }

  verDetalle(f: FacturaDto): void {
    this.service.getFactura(f.id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (full) => (this.facturaDetalle = full),
        error: (err) => (this.errorMessage = `Error: ${err.message}`),
      });
  }
  cerrarDetalle(): void { this.facturaDetalle = null; }

  abrirAsociar(f: FacturaDto): void { this.facturaAsociar = f; }
  cerrarAsociar(): void { this.facturaAsociar = null; }
  onAsociacionGuardada(): void {
    this.facturaAsociar = null;
    this.cargar();
  }

  abrirAplicaciones(f: FacturaDto): void { this.facturaAplicaciones = f; }
  cerrarAplicaciones(): void { this.facturaAplicaciones = null; }
  onAplicacionesCambio(): void {
    this.cargar();
  }

  estadoClass(estado: string): string {
    if (estado === 'procesada') return 'ok';
    if (estado === 'requiere_revision') return 'warn';
    if (estado === 'conflicto') return 'danger';
    return 'danger';
  }

  estadoPagoClass(estado: string | undefined): string {
    if (estado === 'pagada') return 'ok';
    if (estado === 'parcial') return 'warn';
    if (estado === 'requiere_revision') return 'danger';
    return 'muted';
  }

  asociacionResumen(f: FacturaDto): string {
    if (f.estado_asociacion === 'pendiente') return 'Pendiente';
    if (f.estado_asociacion === 'sugerida') return 'Sugerida';
    if (f.estado_asociacion === 'asociada_manual') return 'Manual';
    if (f.estado_asociacion === 'asociada_automatica') return 'Automática';
    return f.estado_asociacion;
  }

  estadoAsociacionClass(estado: string): string {
    if (estado === 'asociada_manual' || estado === 'asociada_automatica') return 'ok';
    if (estado === 'sugerida') return 'warn';
    return 'muted';
  }
}
