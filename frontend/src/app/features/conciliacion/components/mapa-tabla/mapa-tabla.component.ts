import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';

import { DepositanteNodo, FilaTabla } from '../../models/grafo.model';

type OrdenCol = 'arrendatario' | 'propiedad' | 'cc' | 'depositante';
type OrdenDir = 'asc' | 'desc';

@Component({
  selector: 'app-mapa-tabla',
  templateUrl: './mapa-tabla.component.html',
  styleUrls: ['./mapa-tabla.component.scss'],
  standalone: false,
})
export class MapaTablaComponent implements OnChanges {
  @Input() filas: FilaTabla[] = [];
  @Input() depositantesDisponibles: DepositanteNodo[] = [];

  @Output() crear = new EventEmitter<{ arrendatario_id: string; depositante_id: string; depositante_original: string }>();
  @Output() eliminar = new EventEmitter<string>();

  busqueda = '';
  filtroEstado: 'todas' | 'con-depositante' | 'sin-depositante' = 'todas';

  ordenCol: OrdenCol = 'arrendatario';
  ordenDir: OrdenDir = 'asc';

  filasVisibles: FilaTabla[] = [];

  agregarPara: FilaTabla | null = null;
  busquedaDep = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['filas']) this.recalcular();
  }

  recalcular(): void {
    const t = this.busqueda.trim().toLowerCase();
    let out = this.filas.filter((f) => {
      if (this.filtroEstado === 'con-depositante' && !f.depositante_id) return false;
      if (this.filtroEstado === 'sin-depositante' && f.depositante_id) return false;
      if (!t) return true;
      return (
        f.arrendatario_nombre.toLowerCase().includes(t) ||
        f.propiedad_nombre.toLowerCase().includes(t) ||
        f.depositante_nombre.toLowerCase().includes(t) ||
        (f.cc ?? '').toLowerCase().includes(t)
      );
    });

    const dir = this.ordenDir === 'asc' ? 1 : -1;
    out = out.sort((a, b) => {
      const av = this.valor(a, this.ordenCol);
      const bv = this.valor(b, this.ordenCol);
      return av.toLowerCase().localeCompare(bv.toLowerCase()) * dir;
    });

    this.filasVisibles = out;
  }

  private valor(f: FilaTabla, col: OrdenCol): string {
    switch (col) {
      case 'arrendatario': return f.arrendatario_nombre;
      case 'propiedad': return f.propiedad_nombre;
      case 'cc': return f.cc ?? '';
      case 'depositante': return f.depositante_nombre;
    }
  }

  ordenarPor(col: OrdenCol): void {
    if (this.ordenCol === col) {
      this.ordenDir = this.ordenDir === 'asc' ? 'desc' : 'asc';
    } else {
      this.ordenCol = col;
      this.ordenDir = 'asc';
    }
    this.recalcular();
  }

  iconoOrden(col: OrdenCol): string {
    if (this.ordenCol !== col) return 'bi-arrow-down-up';
    return this.ordenDir === 'asc' ? 'bi-sort-down' : 'bi-sort-up';
  }

  abrirAgregar(fila: FilaTabla): void {
    this.agregarPara = fila;
    this.busquedaDep = '';
  }

  cerrarAgregar(): void {
    this.agregarPara = null;
    this.busquedaDep = '';
  }

  deposPara(fila: FilaTabla): DepositanteNodo[] {
    const idsUsados = new Set(
      this.filas
        .filter((x) => x.arrendatario_id === fila.arrendatario_id && x.depositante_id)
        .map((x) => x.depositante_id)
    );
    const t = this.busquedaDep.trim().toLowerCase();
    return this.depositantesDisponibles.filter(
      (d) => !idsUsados.has(d.id) && (!t || d.nombre_original.toLowerCase().includes(t))
    );
  }

  elegir(dep: DepositanteNodo): void {
    if (!this.agregarPara) return;
    this.crear.emit({
      arrendatario_id: this.agregarPara.arrendatario_id,
      depositante_id: dep.id,
      depositante_original: dep.nombre_original,
    });
    this.cerrarAgregar();
  }

  eliminarFila(fila: FilaTabla): void {
    if (!fila.arista_id) return;
    if (!confirm('¿Eliminar esta asociación?')) return;
    this.eliminar.emit(fila.arista_id);
  }
}