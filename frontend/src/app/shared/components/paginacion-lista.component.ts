import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-paginacion-lista',
  standalone: true,
  template: `
    <span aria-live="polite">{{ inicio }}–{{ fin }} de {{ cantidad }}</span>
    @if (paginas > 1) {
      <nav [attr.aria-label]="'Paginación de ' + etiqueta">
        <button type="button" class="btn btn-ghost btn-sm" [disabled]="pagina <= 1"
          (click)="paginaChange.emit(pagina - 1)">Anterior</button>
        <button type="button" class="btn btn-ghost btn-sm" [disabled]="pagina >= paginas"
          (click)="paginaChange.emit(pagina + 1)">Siguiente</button>
      </nav>
    }
  `,
  styles: [`
    :host {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding-top: 12px;
      font-size: 12px;
    }
    nav { display: flex; gap: 4px; }
  `],
})
export class PaginacionListaComponent {
  @Input({ required: true }) cantidad = 0;
  @Input({ required: true }) porPagina = 15;
  @Input({ required: true }) etiqueta = '';
  @Input() pagina = 1;
  @Output() paginaChange = new EventEmitter<number>();

  get paginas(): number {
    return Math.ceil(this.cantidad / this.porPagina);
  }

  get inicio(): number {
    return (this.pagina - 1) * this.porPagina + 1;
  }

  get fin(): number {
    return Math.min(this.pagina * this.porPagina, this.cantidad);
  }
}
