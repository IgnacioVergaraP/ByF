import {
  Component, EventEmitter, Input, OnChanges, OnDestroy, OnInit,
  Output, SimpleChanges,
} from '@angular/core';
import { Subject, finalize, takeUntil } from 'rxjs';

import { ConciliacionService } from '../../services/conciliacion.service';
import { FacturaAsociacionService } from '../../services/factura-asociacion.service';
import { ArrendatarioDto, PropiedadDto } from '../../models/propiedad.model';
import {
  PropiedadCandidataDto,
  SugerenciasFacturaDto,
} from '../../models/asociacion-factura.model';
import { FacturaDto } from '../../models/factura.model';

interface SeleccionPropiedad {
  propiedad_id: string;
  nombre: string;
  conceptosDisponibles: string[];
  conceptosSeleccionados: string[];
  seleccionada: boolean;
}

@Component({
  selector: 'app-asociar-factura',
  templateUrl: './asociar-factura.component.html',
  styleUrls: ['./asociar-factura.component.scss'],
  standalone: false,
})
export class AsociarFacturaComponent implements OnInit, OnChanges, OnDestroy {
  @Input() factura: FacturaDto | null = null;
  @Output() cerrar = new EventEmitter<void>();
  @Output() guardado = new EventEmitter<void>();

  loadingSugerencias = false;
  loadingMaestro = false;
  guardando = false;
  errorMessage: string | null = null;

  sugerencias: SugerenciasFacturaDto | null = null;

  arrendatarios: ArrendatarioDto[] = [];
  propiedades: PropiedadDto[] = [];

  busquedaArrendatario = '';
  arrendatariosFiltrados: ArrendatarioDto[] = [];
  arrendatarioSeleccionado: ArrendatarioDto | null = null;

  propiedadesDelArrendatario: SeleccionPropiedad[] = [];

  private destroy$ = new Subject<void>();

  constructor(
    private conciliacion: ConciliacionService,
    private asociacion: FacturaAsociacionService,
  ) {}

  ngOnInit(): void {
    this.loadMaestro();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['factura'] && this.factura) {
      this.loadSugerencias(this.factura.id);
      this.resetSeleccion();
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadSugerencias(facturaId: string): void {
    this.loadingSugerencias = true;
    this.asociacion
      .getSugerencias(facturaId)
      .pipe(
        finalize(() => (this.loadingSugerencias = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => (this.sugerencias = r),
        error: (err) => (this.errorMessage = `Error: ${err.message}`),
      });
  }

  loadMaestro(): void {
    this.loadingMaestro = true;
    this.conciliacion.getArrendatarios()
      .pipe(takeUntil(this.destroy$))
      .subscribe((r) => (this.arrendatarios = r.items));
    this.conciliacion.getPropiedades()
      .pipe(
        finalize(() => (this.loadingMaestro = false)),
        takeUntil(this.destroy$)
      )
      .subscribe((r) => {
        this.propiedades = r.items;
        this.filtrarArrendatarios();
      });
  }

  filtrarArrendatarios(): void {
    const t = this.busquedaArrendatario.trim().toLowerCase();
    if (!t) {
      this.arrendatariosFiltrados = this.arrendatarios.slice(0, 20);
      return;
    }
    this.arrendatariosFiltrados = this.arrendatarios
      .filter((a) => a.nombre_original.toLowerCase().includes(t))
      .slice(0, 20);
  }

  elegirArrendatario(a: ArrendatarioDto): void {
    this.arrendatarioSeleccionado = a;
    const props = this.propiedades.filter((p) =>
      p.arrendatarios.some((x) => x.id === a.id)
    );
    this.propiedadesDelArrendatario = props.map((p) => ({
      propiedad_id: p.id,
      nombre: p.nombre_original,
      conceptosDisponibles: p.conceptos,
      conceptosSeleccionados: [...p.conceptos],
      seleccionada: false,
    }));
    // Preseleccionar por código detectado
    const codigos = this.sugerencias?.codigos_detectados ?? [];
    if (codigos.length > 0) {
      this.propiedadesDelArrendatario.forEach((sp) => {
        if (codigos.some((c) => sp.nombre.toLowerCase().includes(c.toLowerCase()))) {
          sp.seleccionada = true;
        }
      });
    }
  }

  usarSugerencia(sug: { arrendatario_id: string; propiedades: PropiedadCandidataDto[] }): void {
    const arr = this.arrendatarios.find((a) => a.id === sug.arrendatario_id);
    if (!arr) return;
    this.elegirArrendatario(arr);
    const ids = new Set(sug.propiedades.map((p) => p.id));
    this.propiedadesDelArrendatario.forEach((sp) => {
      if (ids.has(sp.propiedad_id)) sp.seleccionada = true;
    });
  }

  toggleSeleccion(item: SeleccionPropiedad): void {
    item.seleccionada = !item.seleccionada;
  }

  toggleConcepto(item: SeleccionPropiedad, concepto: string): void {
    const i = item.conceptosSeleccionados.indexOf(concepto);
    if (i >= 0) item.conceptosSeleccionados.splice(i, 1);
    else item.conceptosSeleccionados.push(concepto);
  }

  confirmar(): void {
    if (!this.factura || !this.arrendatarioSeleccionado) {
      this.errorMessage = 'Selecciona un arrendatario.';
      return;
    }
    const seleccionadas = this.propiedadesDelArrendatario.filter((p) => p.seleccionada);
    if (seleccionadas.length === 0) {
      this.errorMessage = 'Selecciona al menos una propiedad.';
      return;
    }
    const payload = {
      arrendatario_id: this.arrendatarioSeleccionado.id,
      propiedades: seleccionadas.map((p) => ({
        propiedad_id: p.propiedad_id,
        conceptos: p.conceptosSeleccionados,
      })),
      confirmar_identidad: true,
    };
    this.guardando = true;
    this.asociacion
      .asociar(this.factura.id, payload)
      .pipe(finalize(() => (this.guardando = false)))
      .subscribe({
        next: () => this.guardado.emit(),
        error: (err) => (this.errorMessage = err.error?.error ?? err.message),
      });
  }

  cancelar(): void {
    this.cerrar.emit();
  }

  private resetSeleccion(): void {
    this.arrendatarioSeleccionado = null;
    this.propiedadesDelArrendatario = [];
    this.busquedaArrendatario = '';
    this.errorMessage = null;
  }
}