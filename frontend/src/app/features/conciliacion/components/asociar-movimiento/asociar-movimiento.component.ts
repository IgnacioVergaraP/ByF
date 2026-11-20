import {
  Component, EventEmitter, Input, OnChanges, OnDestroy, OnInit,
  Output, SimpleChanges,
} from '@angular/core';
import { Subject, finalize, takeUntil } from 'rxjs';

import { ConciliacionService } from '../../services/conciliacion.service';
import { AsociacionApiService } from '../../services/asociacion.service';
import {
  ArrendatarioInfoDto,
  PropiedadInfoDto,
  SugerenciasDto,
} from '../../models/asociacion.model';
import { ArrendatarioDto, PropiedadDto } from '../../models/propiedad.model';
import { MovimientoDto } from '../../models/cartola.model';

interface SeleccionPropiedad {
  propiedad_id: string;
  nombre: string;
  conceptosDisponibles: string[];
  conceptosSeleccionados: string[];
  seleccionada: boolean;
}

@Component({
  selector: 'app-asociar-movimiento',
  templateUrl: './asociar-movimiento.component.html',
  styleUrls: ['./asociar-movimiento.component.scss'],
  standalone: false,
})
export class AsociarMovimientoComponent implements OnInit, OnChanges, OnDestroy {
  @Input() movimiento: MovimientoDto | null = null;
  @Input() modo: 'crear' | 'corregir' = 'crear';
  @Output() cerrar = new EventEmitter<void>();
  @Output() guardado = new EventEmitter<void>();

  loadingSugerencias = false;
  loadingMaestro = false;
  guardando = false;
  errorMessage: string | null = null;

  sugerencias: SugerenciasDto | null = null;

  // Maestro para búsqueda
  arrendatarios: ArrendatarioDto[] = [];
  propiedades: PropiedadDto[] = [];

  busquedaArrendatario = '';
  arrendatariosFiltrados: ArrendatarioDto[] = [];
  arrendatarioSeleccionado: ArrendatarioDto | null = null;

  propiedadesDelArrendatario: SeleccionPropiedad[] = [];

  private destroy$ = new Subject<void>();

  constructor(
    private conciliacion: ConciliacionService,
    private asociacionApi: AsociacionApiService,
  ) {}

  ngOnInit(): void {
    this.loadMaestro();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['movimiento'] && this.movimiento) {
      this.loadSugerencias(this.movimiento.id);
      this.resetSeleccion();
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadSugerencias(movimientoId: string): void {
    this.loadingSugerencias = true;
    this.asociacionApi
      .getSugerencias(movimientoId)
      .pipe(
        finalize(() => (this.loadingSugerencias = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (r) => {
          this.sugerencias = r;
          // Si hay coincidencia exacta, precargar el arrendatario
          if (this.modo === 'corregir' && r.coincidencia_exacta?.arrendatario) {
            this.precargarDesdeExacta(r);
          }
        },
        error: (err) => {
          this.errorMessage = `Error cargando sugerencias: ${err.message}`;
        },
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
    const term = this.busquedaArrendatario.trim().toLowerCase();
    if (!term) {
      this.arrendatariosFiltrados = this.arrendatarios.slice(0, 20);
      return;
    }
    this.arrendatariosFiltrados = this.arrendatarios
      .filter((a) => a.nombre_original.toLowerCase().includes(term))
      .slice(0, 20);
  }

  elegirArrendatario(a: ArrendatarioDto): void {
    this.arrendatarioSeleccionado = a;
    this.propiedadesDelArrendatario = this.propiedades
      .filter((p) => p.arrendatarios.some((x) => x.id === a.id))
      .map((p) => ({
        propiedad_id: p.id,
        nombre: p.nombre_original,
        conceptosDisponibles: p.conceptos,
        conceptosSeleccionados: [...p.conceptos],
        seleccionada: false,
      }));
  }

  toggleSeleccion(item: SeleccionPropiedad): void {
    item.seleccionada = !item.seleccionada;
  }

  toggleConcepto(item: SeleccionPropiedad, concepto: string): void {
    const idx = item.conceptosSeleccionados.indexOf(concepto);
    if (idx >= 0) {
      item.conceptosSeleccionados.splice(idx, 1);
    } else {
      item.conceptosSeleccionados.push(concepto);
    }
  }

  confirmar(): void {
    if (!this.movimiento) return;
    if (!this.arrendatarioSeleccionado) {
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
    };
    this.guardando = true;
    const op = this.modo === 'crear'
      ? this.asociacionApi.asociar(this.movimiento.id, payload)
      : this.asociacionApi.corregir(this.movimiento.id, payload);

    op.pipe(finalize(() => (this.guardando = false)))
      .subscribe({
        next: () => {
          this.guardado.emit();
        },
        error: (err) => {
          this.errorMessage = `Error: ${err.error?.error ?? err.message}`;
        },
      });
  }

  cancelar(): void {
    this.cerrar.emit();
  }

  private precargarDesdeExacta(r: SugerenciasDto): void {
    if (!r.coincidencia_exacta?.arrendatario) return;
    const arrId = r.coincidencia_exacta.arrendatario.id;
    const arr = this.arrendatarios.find((a) => a.id === arrId);
    if (!arr) return;
    this.elegirArrendatario(arr);
    const propsIds = new Set(r.coincidencia_exacta.propiedades.map((p) => p.id));
    this.propiedadesDelArrendatario.forEach((sp) => {
      if (propsIds.has(sp.propiedad_id)) sp.seleccionada = true;
    });
  }

  private resetSeleccion(): void {
    this.arrendatarioSeleccionado = null;
    this.propiedadesDelArrendatario = [];
    this.busquedaArrendatario = '';
    this.errorMessage = null;
  }
}