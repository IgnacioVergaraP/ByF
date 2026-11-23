import {
  Component, ElementRef, EventEmitter, OnDestroy, OnInit, Output, ViewChild,
} from '@angular/core';
import { HttpEventType } from '@angular/common/http';
import { Subject, finalize, takeUntil } from 'rxjs';

import { FacturaService } from '../../services/factura.service';
import { EstadoPagoFactura, FacturaDto, FacturaImportResultDto } from '../../models/factura.model';

@Component({
  selector: 'app-facturas-panel',
  templateUrl: './facturas-panel.component.html',
  styleUrls: ['./facturas-panel.component.scss'],
  standalone: false,
})
export class FacturasPanelComponent implements OnInit, OnDestroy {
  @ViewChild('fileInput') fileInput?: ElementRef<HTMLInputElement>;
  @Output() countChange = new EventEmitter<number>();

  archivos: File[] = [];
  procesando = false;
  progreso = 0;
  mensaje: string | null = null;
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

  constructor(private service: FacturaService) {}

  ngOnInit(): void { this.cargar(); }
  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  abrirSelector(): void { this.fileInput?.nativeElement.click(); }

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const lista = input.files;
    if (!lista) return;
    const nuevos: File[] = [];
    for (let i = 0; i < lista.length; i++) {
      const f = lista.item(i);
      if (f && f.name.toLowerCase().endsWith('.pdf')) nuevos.push(f);
    }
    this.archivos = [...this.archivos, ...nuevos];
    input.value = '';
  }

  quitarArchivo(idx: number): void { this.archivos.splice(idx, 1); }
  limpiarSeleccion(): void {
    this.archivos = [];
    this.mensaje = null;
    this.errorMessage = null;
  }

  importar(): void {
    if (this.archivos.length === 0 || this.procesando) return;
    this.procesando = true;
    this.progreso = 0;
    this.mensaje = null;
    this.errorMessage = null;

    this.service.importarLote(this.archivos)
      .pipe(finalize(() => (this.procesando = false)))
      .subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total) {
            this.progreso = Math.round((event.loaded / event.total) * 100);
          } else if (event.type === HttpEventType.Response) {
            const r = event.body as FacturaImportResultDto;
            this.progreso = 100;
            this.mensaje =
              `Lote procesado: ${r.facturas_validas} válidas, ` +
              `${r.facturas_duplicadas} duplicadas, ${r.facturas_con_error} con error.`;
            const errores = r.detalles.flatMap((d) => d.errores);
            if (errores.length > 0) this.errorMessage = errores.join(' · ');
            this.archivos = [];
            this.cargar();
          }
        },
        error: (err) => (this.errorMessage = err.error?.error ?? err.message),
      });
  }

  cargar(): void {
    this.cargando = true;
    this.service.getFacturas()
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
