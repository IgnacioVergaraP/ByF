import { Component, OnDestroy, OnInit } from '@angular/core';
import { HttpEventType } from '@angular/common/http';
import { Subject, finalize, takeUntil } from 'rxjs';

import { ConciliacionService } from '../../services/conciliacion.service';
import { GastosService } from '../../services/gastos.service';
import { CentroCostoDto } from '../../models/propiedad.model';
import {
  GastoDocumentoDto,
  GastoArchivoDto,
  GastoEgresoDto,
  GastosCatalogoDto,
} from '../../models/gasto.model';

type GastoEditable = GastoEgresoDto;

@Component({
  selector: 'app-conciliacion-gastos',
  templateUrl: './gastos.component.html',
  styleUrls: ['./gastos.component.scss'],
  standalone: false,
})
export class GastosComponent implements OnInit, OnDestroy {
  tabActiva: 'cartola' | 'documentos' = 'cartola';
  centros: CentroCostoDto[] = [];
  centroCostoId = '';
  cartola: File | null = null;
  documento: File | null = null;
  catalogo: GastosCatalogoDto = { categorias: {} };
  egresos: GastoEditable[] = [];
  documentos: GastoDocumentoDto[] = [];
  egresosFiltrados: GastoEditable[] = [];
  cartolasCargadas: GastoArchivoDto[] = [];
  excelsCargados: GastoArchivoDto[] = [];
  archivoEliminar: { tipo: 'cartolas' | 'excels'; archivo: GastoArchivoDto } | null = null;
  gastoConciliar: GastoEditable | null = null;
  documentoConciliar: GastoDocumentoDto | null = null;
  egresoSeleccionadoId = '';
  documentoSeleccionadoId = '';
  gastoClasificar: GastoEditable | null = null;
  tipoEdicion: '' | 'fijo' | 'variable' = '';
  categoriaEdicion = '';
  subcategoriaEdicion = '';
  recordarRegla = true;
  periodo = '';
  filtroEstado = 'todos';
  filtroTipo = 'todos';
  filtroCategoria = '';
  filtroSubcategoria = '';
  procesando = false;
  cargando = false;
  error: string | null = null;
  mensaje: string | null = null;

  private destroy$ = new Subject<void>();

  constructor(
    private gastosService: GastosService,
    private conciliacionService: ConciliacionService,
  ) {}

  ngOnInit(): void {
    this.conciliacionService.getCentrosCosto()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (respuesta) => this.centros = respuesta.items,
        error: (err) => this.error = `No se pudieron cargar los centros de costo: ${err.message}`,
      });
    this.gastosService.getCatalogo()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (catalogo) => this.catalogo = catalogo,
        error: (err) => this.error = `No se pudo cargar el catálogo: ${err.message}`,
      });
    this.cargar();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onCartolaSeleccionada(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.cartola = input.files?.[0] ?? null;
    input.value = '';
  }

  onDocumentoSeleccionado(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.documento = input.files?.[0] ?? null;
    input.value = '';
  }

  importarCartola(): void {
    if (!this.cartola || !this.centroCostoId || this.procesando) return;
    this.procesando = true;
    this.error = null;
    this.mensaje = null;
    this.gastosService.importarCartola(this.cartola, this.centroCostoId)
      .pipe(finalize(() => this.procesando = false), takeUntil(this.destroy$))
      .subscribe({
        next: (event) => {
          if (event.type === HttpEventType.Response && event.body) {
            const resultado = event.body;
            this.mensaje = resultado.duplicada
              ? `La cartola ya estaba cargada (${resultado.cantidad_cargos} cargos).`
              : `Cartola procesada. Se importaron ${resultado.cantidad_cargos} cargos.`;
            this.cartola = null;
            this.cargar();
          }
        },
        error: (err) => this.error = err.error?.error ?? err.message,
      });
  }

  subirDocumento(): void {
    if (!this.documento || !this.centroCostoId || this.procesando) return;
    this.procesando = true;
    this.error = null;
    this.mensaje = null;
    this.gastosService.subirDocumento(
      this.documento, this.centroCostoId
    ).pipe(finalize(() => this.procesando = false), takeUntil(this.destroy$))
      .subscribe({
        next: (resultado) => {
          this.mensaje = resultado.duplicada
            ? 'El Excel ya estaba cargado. Se revisaron sus coincidencias.'
            : `${resultado.cantidad_gastos} gastos importados: ${resultado.conciliados} conciliados, ${resultado.pendientes_aprobacion} pendientes de aprobación y ${resultado.sin_coincidencia} sin coincidencia.`;
          this.documento = null;
          this.cargar();
        },
        error: (err) => this.error = err.error?.error ?? err.message,
      });
  }

  cargar(): void {
    this.cargando = true;
    this.gastosService.getArchivos(this.centroCostoId || undefined)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (respuesta) => {
          this.cartolasCargadas = respuesta.cartolas;
          this.excelsCargados = respuesta.excels;
        },
        error: (err) => this.error = `No se pudieron cargar los archivos: ${err.message}`,
      });
    this.gastosService.getEgresos(this.centroCostoId || undefined)
      .pipe(finalize(() => this.cargando = false), takeUntil(this.destroy$))
      .subscribe({
        next: (respuesta) => {
          this.egresos = respuesta.items;
          this.aplicarFiltros();
        },
        error: (err) => this.error = `No se pudieron cargar los egresos: ${err.message}`,
      });
    this.gastosService.getDocumentos(this.centroCostoId || undefined)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (respuesta) => this.documentos = respuesta.items,
        error: (err) => this.error = `No se pudieron cargar los gastos del Excel: ${err.message}`,
      });
  }

  solicitarEliminarArchivo(tipo: 'cartolas' | 'excels', archivo: GastoArchivoDto): void {
    if (this.procesando) return;
    this.archivoEliminar = { tipo, archivo };
  }

  cancelarEliminarArchivo(): void {
    if (!this.procesando) this.archivoEliminar = null;
  }

  confirmarEliminarArchivo(): void {
    const seleccion = this.archivoEliminar;
    if (!seleccion || this.procesando) return;
    this.procesando = true;
    this.error = null;
    this.mensaje = null;
    this.gastosService.eliminarArchivo(seleccion.tipo, seleccion.archivo.id)
      .pipe(finalize(() => this.procesando = false), takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.mensaje = seleccion.tipo === 'cartolas'
            ? `Se eliminaron los cargos y conciliaciones de ${seleccion.archivo.archivo_nombre}.`
            : `Se eliminó ${seleccion.archivo.archivo_nombre} con todas sus filas y conciliaciones.`;
          this.archivoEliminar = null;
          this.cerrarConciliacion();
          this.cerrarClasificacion();
          this.cargar();
        },
        error: (err) => {
          this.error = err.error?.error ?? err.message;
          this.archivoEliminar = null;
        },
      });
  }

  centroCostoCambio(): void {
    this.cargar();
  }

  subcategorias(): string[] {
    return this.catalogo.categorias[this.categoriaEdicion] ?? [];
  }

  tipoCambio(): void {
    if (this.tipoEdicion === 'variable') {
      this.categoriaEdicion = '';
      this.subcategoriaEdicion = '';
    }
  }

  categoriaCambio(): void {
    this.subcategoriaEdicion = '';
  }

  abrirClasificacion(gasto: GastoEditable): void {
    this.gastoClasificar = gasto;
    this.tipoEdicion = gasto.tipo_gasto ?? gasto.sugerencia?.tipo_gasto ?? '';
    this.categoriaEdicion = gasto.categoria ?? gasto.sugerencia?.categoria ?? '';
    this.subcategoriaEdicion = gasto.subcategoria ?? gasto.sugerencia?.subcategoria ?? '';
    this.recordarRegla = true;
  }

  revertirClasificacion(): void {
    const gasto = this.gastoClasificar;
    if (!gasto) return;
    this.gastosService.desclasificar(gasto.id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.mensaje = 'Clasificación revertida. La regla guardada se conserva para futuros movimientos.';
          this.cerrarClasificacion();
          this.cargar();
        },
        error: (err) => this.error = err.error?.error ?? err.message,
      });
  }

  cerrarClasificacion(): void {
    this.gastoClasificar = null;
  }

  guardarClasificacion(): void {
    const gasto = this.gastoClasificar;
    if (!gasto || !this.tipoEdicion) {
      this.error = 'Selecciona si el gasto es fijo o variable.';
      return;
    }
    this.gastosService.clasificar(
      gasto, this.tipoEdicion,
      this.tipoEdicion === 'fijo' ? this.categoriaEdicion : null,
      this.tipoEdicion === 'fijo' ? this.subcategoriaEdicion : null,
      this.recordarRegla,
    ).pipe(takeUntil(this.destroy$)).subscribe({
      next: () => {
        this.mensaje = 'Clasificación guardada.';
        this.cerrarClasificacion();
        this.cargar();
      },
      error: (err) => this.error = err.error?.error ?? err.message,
    });
  }

  abrirConciliacion(gasto: GastoEditable): void {
    this.gastoConciliar = gasto;
    this.documentoConciliar = null;
    this.egresoSeleccionadoId = gasto.id;
    this.documentoSeleccionadoId =
      gasto.documentos.find((doc) => doc.estado_asociacion === 'confirmada')?.id
      ?? gasto.documentos.find((doc) => doc.estado_asociacion === 'sugerida')?.id
      ?? '';
  }

  abrirConciliacionDesdeDocumento(documento: GastoDocumentoDto): void {
    this.documentoConciliar = documento;
    this.gastoConciliar = null;
    this.documentoSeleccionadoId = documento.id;
    const asociacion = documento.asociaciones.find((item) => item.estado === 'confirmada')
      ?? documento.asociaciones.find((item) => item.estado === 'sugerida');
    this.egresoSeleccionadoId = asociacion?.egreso_id ?? '';
  }

  cerrarConciliacion(): void {
    this.gastoConciliar = null;
    this.documentoConciliar = null;
    this.egresoSeleccionadoId = '';
    this.documentoSeleccionadoId = '';
  }

  confirmarConciliacion(): void {
    if (!this.egresoSeleccionadoId || !this.documentoSeleccionadoId) {
      this.error = 'Selecciona un egreso y un gasto del Excel.';
      return;
    }
    this.gastosService.asociar(
      this.egresoSeleccionadoId, this.documentoSeleccionadoId, true,
    )
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.mensaje = 'Gasto del Excel asociado y egreso conciliado.';
          this.cerrarConciliacion();
          this.cargar();
        },
        error: (err) => this.error = err.error?.error ?? err.message,
      });
  }

  asociacionSeleccionadaId(): string | null {
    if (this.gastoConciliar) {
      return this.gastoConciliar.documentos.find(
        (documento) => documento.id === this.documentoSeleccionadoId,
      )?.asociacion_id ?? null;
    }
    if (this.documentoConciliar) {
      return this.documentoConciliar.asociaciones.find(
        (asociacion) => asociacion.egreso_id === this.egresoSeleccionadoId,
      )?.id ?? null;
    }
    return null;
  }

  revertirConciliacion(): void {
    const asociacionId = this.asociacionSeleccionadaId();
    if (!asociacionId) return;
    this.gastosService.desasociar(asociacionId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.mensaje = 'Asociación revertida. El gasto quedó pendiente de conciliación.';
          this.cerrarConciliacion();
          this.cargar();
        },
        error: (err) => this.error = err.error?.error ?? err.message,
      });
  }

  aplicarFiltros(): void {
    const selectedMonth = this.periodo;
    this.egresosFiltrados = this.egresos.filter((gasto) => {
      const month = gasto.fecha.slice(0, 7);
      return (!selectedMonth || month === selectedMonth)
        && (this.filtroEstado === 'todos' || gasto.estado_conciliacion === this.filtroEstado)
        && (this.filtroTipo === 'todos'
          || (this.filtroTipo === 'sin_clasificar' && !gasto.tipo_gasto)
          || gasto.tipo_gasto === this.filtroTipo)
        && (!this.filtroCategoria || gasto.categoria === this.filtroCategoria)
        && (!this.filtroSubcategoria || gasto.subcategoria === this.filtroSubcategoria);
    });
  }

  descargarDocumento(documento: GastoDocumentoDto): void {
    window.open(
      `/api/conciliacion/gastos/documentos/${documento.id}/descargar`,
      '_blank',
    );
  }

  descargarDocumentoPorId(id: string): void {
    const documento = this.documentos.find((item) => item.id === id);
    if (documento) this.descargarDocumento(documento);
  }

  seleccionarTab(tab: 'cartola' | 'documentos'): void {
    this.tabActiva = tab;
  }

  egresoResumen(egresoId: string): string {
    const egreso = this.egresos.find((item) => item.id === egresoId);
    return egreso ? `${egreso.fecha} · ${egreso.descripcion_original} · $${egreso.monto}` : egresoId;
  }

  centroCodigo(id: string): string {
    return this.centros.find((centro) => centro.id === id)?.codigo ?? id;
  }

  documentosDisponibles(gasto: GastoEditable): GastoDocumentoDto[] {
    return this.documentos.filter((documento) =>
      documento.centro_costo_id === gasto.centro_costo_id
      && documento.monto === gasto.monto
      && !documento.asociaciones.some((asociacion) =>
        asociacion.egreso_id !== gasto.id && asociacion.estado === 'confirmada'
      )
    );
  }

  egresosDisponibles(documento: GastoDocumentoDto): GastoEditable[] {
    return this.egresos.filter((egreso) =>
      egreso.centro_costo_id === documento.centro_costo_id
      && egreso.monto === documento.monto
      && !egreso.documentos.some((doc) =>
        doc.estado_asociacion === 'confirmada' && doc.id !== documento.id
      )
    );
  }

  estadoRegistro(documento: GastoDocumentoDto): string {
    if (documento.estado === 'pagado') return 'Conciliado';
    return documento.asociaciones.length ? 'Pendiente de aprobación' : 'Sin coincidencia';
  }

  clasificacionOrigen(gasto: GastoEditable): string {
    if (gasto.clasificacion_origen === 'automatica') {
      return `Automática · regla: ${gasto.regla?.valor ?? ''}`;
    }
    return 'Manual';
  }
}
