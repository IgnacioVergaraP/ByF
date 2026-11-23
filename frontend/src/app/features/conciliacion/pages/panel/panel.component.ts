import { Component, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { HttpEventType } from '@angular/common/http';
import { Subject, finalize, takeUntil } from 'rxjs';

import { CartolaService } from '../../services/cartola.service';
import { AsociacionApiService } from '../../services/asociacion.service';
import { ConciliacionService } from '../../services/conciliacion.service';
import { FacturaService } from '../../services/factura.service';
import { FacturasPanelComponent } from '../../components/facturas-panel/facturas-panel.component';
import {
  CartolaImportResultDto,
  CentroCostoRefDto,
  MovimientoDto,
} from '../../models/cartola.model';
import { CentroCostoDto } from '../../models/propiedad.model';
import { ExcedenteDto } from '../../models/aplicacion-pago.model';

type Tab = 'movimientos' | 'facturas';

@Component({
  selector: 'app-conciliacion-panel',
  templateUrl: './panel.component.html',
  styleUrls: ['./panel.component.scss'],
  standalone: false
})
export class PanelComponent implements OnInit, OnDestroy {
  @ViewChild(FacturasPanelComponent) private facturasPanel?: FacturasPanelComponent;

  tabActiva: Tab = 'movimientos';
  facturasVisitadas = false;
  cargaCartolaAbierta = false;
  cargaFacturasAbierta = false;
  facturasSeleccionadas: File[] = [];
  procesandoFacturas = false;
  progresoFacturas = 0;
  mensajeCargaFacturas: string | null = null;
  errorCargaFacturas: string | null = null;

  cartolaSeleccionada: File | null = null;
  centroCostoSeleccionadoId: string | null = null;
  centrosDisponibles: CentroCostoDto[] = [];

  panelPropiedadesAbierto = false;
  panelLimpiarAbierto = false;

  panelAsociacionAbierto = false;
  movimientoSeleccionado: MovimientoDto | null = null;
  modoAsociacion: 'crear' | 'corregir' = 'crear';

  panelAplicarPagoAbierto = false;
  movimientoParaPagar: MovimientoDto | null = null;

  procesando = false;
  progreso = 0;
  mensajeResultado: string | null = null;
  errorMensaje: string | null = null;

  movimientos: MovimientoDto[] = [];
  movimientosFiltrados: MovimientoDto[] = [];
  busqueda = '';
  filtroEstado = 'todos';
  periodoMovimiento = '';
  paginaMovimientos = 1;
  readonly movimientosPorPagina = 15;
  cargandoMovimientos = false;

  centrosEnMovimientos: CentroCostoRefDto[] = [];
  filtroCC: string | null = null;

  totalDepositos = 0;
  asociados = 0;
  pendientes = 0;
  montoTotal = 0;

  facturasCount = 0;

  private destroy$ = new Subject<void>();

  constructor(
    private cartolaService: CartolaService,
    private asociacionApi: AsociacionApiService,
    private conciliacion: ConciliacionService,
    private facturaService: FacturaService,
  ) {}

  ngOnInit(): void {
    this.loadCentrosDisponibles();
    this.loadMovimientos();
    this.loadCentrosEnMovimientos();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  cambiarTab(tab: Tab): void {
    this.tabActiva = tab;
    if (tab === 'facturas') this.facturasVisitadas = true;
  }
  onFacturasCountChange(count: number): void { this.facturasCount = count; }

  loadCentrosDisponibles(): void {
    this.conciliacion.getCentrosCosto()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (r) => (this.centrosDisponibles = r.items),
        error: () => (this.centrosDisponibles = []),
      });
  }

  loadCentrosEnMovimientos(): void {
    this.cartolaService.getCentrosCostoEnMovimientos()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (r) => (this.centrosEnMovimientos = r.items),
        error: () => (this.centrosEnMovimientos = []),
      });
  }

  onCartolaInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.cartolaSeleccionada = file;
    this.errorMensaje = null;
    this.mensajeResultado = null;
    input.value = '';
  }

  onCentroCostoChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.centroCostoSeleccionadoId = select.value || null;
  }

  get puedeProcesar(): boolean {
    return !!this.cartolaSeleccionada && !!this.centroCostoSeleccionadoId && !this.procesando;
  }

  subirCartola(): void {
    if (!this.cartolaSeleccionada || !this.centroCostoSeleccionadoId) {
      this.errorMensaje = 'Debes seleccionar un archivo y un centro de costo.';
      return;
    }
    this.procesando = true;
    this.progreso = 0;
    this.errorMensaje = null;
    this.mensajeResultado = null;

    this.cartolaService.importCartola(this.cartolaSeleccionada, this.centroCostoSeleccionadoId)
      .pipe(finalize(() => (this.procesando = false)))
      .subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total) {
            this.progreso = Math.round((event.loaded / event.total) * 100);
          } else if (event.type === HttpEventType.Response) {
            const r = event.body as CartolaImportResultDto;
            this.progreso = 100;
            this.mensajeResultado = r.duplicada
              ? `La cartola ya había sido procesada (${r.cantidad_movimientos} movimientos).`
              : `Cartola procesada: ${r.cantidad_movimientos} movimientos. Validación: ${r.validacion_ok ? 'OK' : r.validacion_mensaje}`;
            this.cartolaSeleccionada = null;
            this.centroCostoSeleccionadoId = null;
            this.cargaCartolaAbierta = false;
            this.loadMovimientos();
            this.loadCentrosEnMovimientos();
          }
        },
        error: (err) => (this.errorMensaje = err.error?.error ?? err.message),
      });
  }

  onFacturasSeleccionadas(event: Event): void {
    const input = event.target as HTMLInputElement;
    const pdfs = Array.from(input.files ?? []).filter((archivo) => archivo.name.toLowerCase().endsWith('.pdf'));
    this.facturasSeleccionadas = [...this.facturasSeleccionadas, ...pdfs];
    input.value = '';
  }

  quitarFacturaSeleccionada(indice: number): void {
    this.facturasSeleccionadas.splice(indice, 1);
  }

  limpiarFacturasSeleccionadas(): void {
    this.facturasSeleccionadas = [];
    this.mensajeCargaFacturas = null;
    this.errorCargaFacturas = null;
  }

  importarFacturas(): void {
    if (!this.facturasSeleccionadas.length || this.procesandoFacturas) return;
    this.procesandoFacturas = true;
    this.progresoFacturas = 0;
    this.mensajeCargaFacturas = null;
    this.errorCargaFacturas = null;

    this.facturaService.importarLote(this.facturasSeleccionadas)
      .pipe(takeUntil(this.destroy$), finalize(() => this.procesandoFacturas = false))
      .subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total) {
            this.progresoFacturas = Math.round((event.loaded / event.total) * 100);
          } else if (event.type === HttpEventType.Response && event.body) {
            const resultado = event.body;
            this.progresoFacturas = 100;
            this.mensajeCargaFacturas =
              `Lote procesado: ${resultado.facturas_validas} válidas, ` +
              `${resultado.facturas_duplicadas} duplicadas, ${resultado.facturas_con_error} con error.`;
            const errores = resultado.detalles.flatMap((detalle) => detalle.errores);
            if (errores.length) this.errorCargaFacturas = errores.join(' · ');
            this.facturasSeleccionadas = [];
            if (!resultado.facturas_con_error && (resultado.facturas_validas || resultado.facturas_duplicadas)) {
              this.cargaFacturasAbierta = false;
            }
            this.facturasPanel?.cargar();
          }
        },
        error: (err) => this.errorCargaFacturas = err.error?.error ?? err.message,
      });
  }

  loadMovimientos(): void {
    this.cargandoMovimientos = true;
    this.cartolaService.getMovimientos()
      .pipe(
        finalize(() => (this.cargandoMovimientos = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.movimientos = r.items;
          this.totalDepositos = r.total;
          this.asociados = r.asociados;
          this.pendientes = r.pendientes;
          this.montoTotal = r.total_abonos;
          this.aplicarFiltros(this.paginaMovimientos);
        },
        error: (err) => (this.errorMensaje = `Error: ${err.message}`),
      });
  }

  seleccionarCC(ccId: string | null): void {
    this.filtroCC = ccId;
    this.aplicarFiltros();
  }

  conteoPorCC(ccId: string): number {
    return this.movimientos.filter((m) => m.centro_costo?.id === ccId).length;
  }

  aplicarFiltros(pagina = 1): void {
    const term = this.busqueda.trim().toLowerCase();
    this.movimientosFiltrados = this.movimientos.filter((m) => {
      const matchEstado = this.filtroEstado === 'todos'
        || m.estado === this.filtroEstado
        || (this.filtroEstado === 'asociado' && m.estado.startsWith('asociado'));
      const matchTerm = !term
        || (m.depositante_original ?? '').toLowerCase().includes(term)
        || m.descripcion_original.toLowerCase().includes(term)
        || (m.factura_folio ?? '').toLowerCase().includes(term)
        || m.facturas_relacionadas.some((factura) => factura.folio.toLowerCase().includes(term))
        || m.arrendatarios.some((arrendatario) => arrendatario.nombre_original.toLowerCase().includes(term));
      const matchCC = this.filtroCC === null || m.centro_costo?.id === this.filtroCC;
      return matchEstado && matchTerm && matchCC
        && (!this.periodoMovimiento || m.fecha.startsWith(this.periodoMovimiento));
    });
    const ultimaPagina = Math.max(1, Math.ceil(this.movimientosFiltrados.length / this.movimientosPorPagina));
    this.paginaMovimientos = Math.min(pagina, ultimaPagina);
  }

  abrirPanelPropiedades(): void { this.panelPropiedadesAbierto = true; }
  cerrarPanelPropiedades(): void { this.panelPropiedadesAbierto = false; }
  abrirPanelLimpiar(): void { this.panelLimpiarAbierto = true; }
  cerrarPanelLimpiar(): void { this.panelLimpiarAbierto = false; }

  onLimpiezaCompletada(): void {
    this.panelLimpiarAbierto = false;
    this.mensajeResultado = 'Registros eliminados.';
    this.loadMovimientos();
    this.loadCentrosEnMovimientos();
  }

  abrirPanelAsociacion(m: MovimientoDto): void {
    this.movimientoSeleccionado = m;
    this.modoAsociacion = m.estado === 'pendiente' ? 'crear' : 'corregir';
    this.panelAsociacionAbierto = true;
  }
  cerrarPanelAsociacion(): void {
    this.panelAsociacionAbierto = false;
    this.movimientoSeleccionado = null;
  }
  onAsociacionGuardada(): void {
    this.cerrarPanelAsociacion();
    this.loadMovimientos();
    this.loadCentrosEnMovimientos();
  }

  abrirPanelAplicarPago(m: MovimientoDto): void {
    this.movimientoParaPagar = m;
    this.panelAplicarPagoAbierto = true;
  }
  cerrarPanelAplicarPago(): void {
    this.panelAplicarPagoAbierto = false;
    this.movimientoParaPagar = null;
  }
  onPagoGuardado(excedente: ExcedenteDto | null): void {
    const puedeSeguirAplicando = !!excedente && excedente.monto_disponible > 0
      && excedente.facturas_candidatas.length > 0;
    if (!puedeSeguirAplicando) this.cerrarPanelAplicarPago();
    this.loadMovimientos();
  }

  desasociar(m: MovimientoDto): void {
    if (!confirm(`¿Desasociar el movimiento de ${m.depositante_original ?? 'sin depositante'}?`)) return;
    this.asociacionApi.desasociar(m.id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.loadMovimientos();
          this.loadCentrosEnMovimientos();
        },
        error: (err) => (this.errorMensaje = `Error: ${err.message}`),
      });
  }

  esPendiente(m: MovimientoDto): boolean { return m.estado === 'pendiente'; }
  esAsociado(m: MovimientoDto): boolean { return m.estado.startsWith('asociado'); }

  arrendatariosResumen(m: MovimientoDto): string {
    if (!m.arrendatarios || m.arrendatarios.length === 0) return '—';
    if (m.arrendatarios.length === 1) return m.arrendatarios[0].nombre_original;
    if (m.arrendatarios.length === 2) {
      return `${m.arrendatarios[0].nombre_original}, ${m.arrendatarios[1].nombre_original}`;
    }
    return `${m.arrendatarios[0].nombre_original} y ${m.arrendatarios.length - 1} más`;
  }

  etiquetaFactura(m: MovimientoDto): string {
    return m.factura_folio ? `N° ${m.factura_folio}` : '—';
  }

    etiquetaTotalidad(m: MovimientoDto): string {
    if (!m.factura_totalidad) return '—';
    if (m.factura_totalidad === 'aplicado_total') return 'Aplicado';
    if (m.factura_totalidad === 'aplicado_parcial') return 'Parcial';
    return 'Sin aplicar';
    }

    totalidadClass(m: MovimientoDto): string {
    if (m.factura_totalidad === 'aplicado_total') return 'total';
    if (m.factura_totalidad === 'aplicado_parcial') return 'parcial';
    return 'muted';
    }

  puedeAplicar(m: MovimientoDto): boolean {
    return (m.disponible ?? 0) > 0;
  }
}
