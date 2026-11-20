import { Component, OnDestroy, OnInit } from '@angular/core';
import { HttpEventType } from '@angular/common/http';
import { FormControl } from '@angular/forms';
import { Subject, combineLatest, of } from 'rxjs';
import {
  catchError,
  debounceTime,
  finalize,
  startWith,
  takeUntil
} from 'rxjs/operators';

import { ConciliacionService } from '../../services/conciliacion.service';
import {
  CentroCostoDto,
  ImportResultDto,
  PropiedadDto
} from '../../models/propiedad.model';

@Component({
  selector: 'app-administrar-propiedades',
  templateUrl: './administrar-propiedades.component.html',
  styleUrls: ['./administrar-propiedades.component.scss'],
  standalone: false
})
export class AdministrarPropiedadesComponent implements OnInit, OnDestroy {
  loading = false;
  importing = false;
  importProgress = 0;
  errorMessage: string | null = null;
  importMessage: string | null = null;

  propiedades: PropiedadDto[] = [];
  centros: CentroCostoDto[] = [];
  filteredPropiedades: PropiedadDto[] = [];

  filtroCC = new FormControl<string>('');
  busqueda = new FormControl<string>('');

  private destroy$ = new Subject<void>();

  constructor(private service: ConciliacionService) {}

  ngOnInit(): void {
    this.loadData();

    combineLatest([
      this.filtroCC.valueChanges.pipe(startWith('')),
      this.busqueda.valueChanges.pipe(startWith(''), debounceTime(200))
    ])
      .pipe(takeUntil(this.destroy$))
      .subscribe(([cc, term]) => this.applyFilters(cc ?? '', term ?? ''));
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadData(): void {
    this.loading = true;
    this.errorMessage = null;

    combineLatest([
      this.service.getPropiedades().pipe(
        catchError((err) => {
          this.errorMessage = `Error cargando propiedades: ${err.message ?? err}`;
          return of({ total: 0, items: [] as PropiedadDto[] });
        })
      ),
      this.service.getCentrosCosto().pipe(
        catchError(() => of({ total: 0, items: [] as CentroCostoDto[] }))
      )
    ])
      .pipe(finalize(() => (this.loading = false)))
      .subscribe(([props, centros]) => {
        this.propiedades = props.items;
        this.centros = centros.items;
        this.applyFilters(this.filtroCC.value ?? '', this.busqueda.value ?? '');
      });
  }

  applyFilters(cc: string, term: string): void {
    const termNorm = (term ?? '').trim().toLowerCase();
    this.filteredPropiedades = this.propiedades.filter((p) => {
      const matchCC = !cc || p.centro_costo?.codigo === cc;
      const matchTerm =
        !termNorm ||
        p.nombre_original.toLowerCase().includes(termNorm) ||
        p.arrendatarios.some((a) =>
          a.nombre_original.toLowerCase().includes(termNorm)
        );
      return matchCC && matchTerm;
    });
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.importing = true;
    this.importProgress = 0;
    this.importMessage = null;
    this.errorMessage = null;

    this.service
      .importMaestro(file)
      .pipe(finalize(() => (this.importing = false)))
      .subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total) {
            this.importProgress = Math.round((event.loaded / event.total) * 100);
          } else if (event.type === HttpEventType.Response) {
            const result = event.body as ImportResultDto;
            this.importMessage =
              `Importación finalizada: ${result.imported_rows} filas importadas, ` +
              `${result.skipped_rows} omitidas, ${result.errors.length} errores.`;
            this.loadData();
          }
        },
        error: (err) => {
          this.errorMessage = `Error importando: ${err.error?.error ?? err.message}`;
        }
      });

    input.value = '';
  }

  clearFilters(): void {
    this.filtroCC.setValue('');
    this.busqueda.setValue('');
  }

  trackById(_: number, item: PropiedadDto): string {
    return item.id;
  }
}