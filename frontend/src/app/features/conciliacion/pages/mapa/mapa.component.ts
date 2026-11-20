import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subject, finalize, takeUntil } from 'rxjs';

import { GrafoApiService } from '../../services/grafo.service';
import { AsociacionApiService } from '../../services/asociacion.service';
import {
  ArrendatarioConRelaciones,
  DepositanteNodo,
  FilaTabla,
  GrafoDto,
  VistaMapa,
} from '../../models/grafo.model';

@Component({
  selector: 'app-conciliacion-mapa',
  templateUrl: './mapa.component.html',
  styleUrls: ['./mapa.component.scss'],
  standalone: false,
})
export class MapaComponent implements OnInit, OnDestroy {
  grafo: GrafoDto | null = null;
  loading = true;
  errorMessage: string | null = null;
  vista: VistaMapa = 'tarjetas';

  // Datos procesados
  tarjetas: ArrendatarioConRelaciones[] = [];
  filasTabla: FilaTabla[] = [];
  depositantesDisponibles: DepositanteNodo[] = [];

  private destroy$ = new Subject<void>();

  constructor(
    private grafoApi: GrafoApiService,
    private asociacionApi: AsociacionApiService,
  ) {}

  ngOnInit(): void {
    this.cargar();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  cambiarVista(v: VistaMapa): void {
    this.vista = v;
  }

  cargar(): void {
    this.loading = true;
    this.errorMessage = null;
    this.grafoApi
      .getGrafo()
      .pipe(
        finalize(() => (this.loading = false)),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (g) => {
          this.grafo = g;
          this.depositantesDisponibles = g.depositantes;
          this.tarjetas = this.grafoApi.construirTarjetas(g);
          this.filasTabla = this.grafoApi.construirTabla(g);
        },
        error: (err) => (this.errorMessage = `Error: ${err.message}`),
      });
  }

  onCrear(evt: { arrendatario_id: string; depositante_id: string; depositante_original: string }): void {
    this.asociacionApi
      .crearAsociacionDirecta(evt.arrendatario_id, evt.depositante_id, evt.depositante_original)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => this.cargar(),
        error: (err) => alert(`Error: ${err.error?.error ?? err.message}`),
      });
  }

  onEliminar(aristaId: string): void {
    this.asociacionApi
      .eliminarAsociacionDirecta(aristaId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => this.cargar(),
        error: (err) => alert(`Error: ${err.error?.error ?? err.message}`),
      });
  }
}