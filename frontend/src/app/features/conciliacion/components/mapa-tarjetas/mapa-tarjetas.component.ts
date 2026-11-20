import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';

import {
  ArrendatarioConRelaciones,
  DepositanteNodo,
} from '../../models/grafo.model';

@Component({
  selector: 'app-mapa-tarjetas',
  templateUrl: './mapa-tarjetas.component.html',
  styleUrls: ['./mapa-tarjetas.component.scss'],
  standalone: false,
})
export class MapaTarjetasComponent implements OnChanges {
  @Input() tarjetas: ArrendatarioConRelaciones[] = [];
  @Input() depositantesDisponibles: DepositanteNodo[] = [];

  @Output() crear = new EventEmitter<{ arrendatario_id: string; depositante_id: string; depositante_original: string }>();
  @Output() eliminar = new EventEmitter<string>(); // arista_id

  busqueda = '';
  tarjetasFiltradas: ArrendatarioConRelaciones[] = [];
  expandidas = new Set<string>();

  // Estado por tarjeta para el dropdown de "agregar depositante"
  dropAbiertoPara: string | null = null;
  dropBusqueda = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['tarjetas']) {
      this.aplicarFiltro();
    }
  }

  aplicarFiltro(): void {
    const t = this.busqueda.trim().toLowerCase();
    if (!t) {
      this.tarjetasFiltradas = this.tarjetas;
      return;
    }
    this.tarjetasFiltradas = this.tarjetas.filter(
      (x) =>
        x.arrendatario.nombre_original.toLowerCase().includes(t) ||
        x.propiedades.some((p) => p.nombre_original.toLowerCase().includes(t)) ||
        x.depositantes.some((d) => d.nombre_original.toLowerCase().includes(t))
    );
  }

  toggleExpandir(id: string): void {
    if (this.expandidas.has(id)) this.expandidas.delete(id);
    else this.expandidas.add(id);
  }

  estaExpandida(id: string): boolean {
    return this.expandidas.has(id);
  }

  abrirDropdown(arrId: string): void {
    this.dropAbiertoPara = this.dropAbiertoPara === arrId ? null : arrId;
    this.dropBusqueda = '';
  }

  cerrarDropdown(): void {
    this.dropAbiertoPara = null;
    this.dropBusqueda = '';
  }

  depositantesPara(tarjeta: ArrendatarioConRelaciones): DepositanteNodo[] {
    const ya = new Set(tarjeta.depositantes.map((d) => d.depositante_id));
    const t = this.dropBusqueda.trim().toLowerCase();
    return this.depositantesDisponibles.filter(
      (d) => !ya.has(d.id) && (!t || d.nombre_original.toLowerCase().includes(t))
    );
  }

  elegirDepositante(
    arrendatario_id: string,
    dep: DepositanteNodo
  ): void {
    this.crear.emit({
      arrendatario_id,
      depositante_id: dep.id,
      depositante_original: dep.nombre_original,
    });
    this.cerrarDropdown();
  }

  eliminarDeposito(arista_id: string): void {
    if (!confirm('¿Eliminar esta asociación?')) return;
    this.eliminar.emit(arista_id);
  }

  trackArr(_: number, x: ArrendatarioConRelaciones): string {
    return x.arrendatario.id;
  }
}