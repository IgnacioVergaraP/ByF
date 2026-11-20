import { Component, EventEmitter, Output } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { finalize } from 'rxjs';

interface Opcion {
  key: 'movimientos' | 'cartolas' | 'cuentas' | 'asociaciones' | 'facturas';
  titulo: string;
  descripcion: string;
  seleccionada: boolean;
  requiere?: Array<Opcion['key']>;
}

@Component({
  selector: 'app-limpiar-modal',
  templateUrl: './limpiar-modal.component.html',
  styleUrls: ['./limpiar-modal.component.scss'],
  standalone: false,
})
export class LimpiarModalComponent {
  @Output() cerrar = new EventEmitter<void>();
  @Output() limpiado = new EventEmitter<void>();

  private readonly baseUrl = '/api/conciliacion';

  opciones: Opcion[] = [
    {
      key: 'movimientos',
      titulo: 'Movimientos bancarios',
      descripcion: 'Borra los abonos extraídos de todas las cartolas. También elimina el historial y los vínculos a propiedades de esos movimientos.',
      seleccionada: false,
    },
    {
      key: 'cartolas',
      titulo: 'Cartolas procesadas',
      descripcion: 'Borra el registro de los PDFs cargados. Requiere borrar también los movimientos.',
      seleccionada: false,
      requiere: ['movimientos'],
    },
    {
      key: 'cuentas',
      titulo: 'Cuentas bancarias',
      descripcion: 'Borra las cuentas registradas. Requiere borrar también las cartolas.',
      seleccionada: false,
      requiere: ['cartolas'],
    },
    {
      key: 'facturas',
      titulo: 'Facturas importadas',
      descripcion: 'Borra las facturas, sus detalles, sus aplicaciones de pago e importaciones. No borra el maestro ni las asociaciones de depositantes.',
      seleccionada: false,
    },
    {
      key: 'asociaciones',
      titulo: 'Asociaciones aprendidas',
      descripcion: 'Borra las identidades tributarias (RUT → arrendatario) y las asociaciones depositante → arrendatario. El sistema "olvidará" los aprendizajes.',
      seleccionada: false,
    },
  ];

  procesando = false;
  errorMessage: string | null = null;

  constructor(private http: HttpClient) {}

  toggle(op: Opcion): void {
    op.seleccionada = !op.seleccionada;
    if (!op.seleccionada) {
      this.opciones.forEach((o) => {
        if (o.requiere?.includes(op.key) && o.seleccionada) {
          o.seleccionada = false;
        }
      });
    }
    if (op.seleccionada && op.requiere) {
      this.opciones.forEach((o) => {
        if (op.requiere!.includes(o.key)) o.seleccionada = true;
      });
    }
  }

  get haySeleccion(): boolean {
    return this.opciones.some((o) => o.seleccionada);
  }

  get resumen(): string {
    const sel = this.opciones.filter((o) => o.seleccionada).map((o) => o.titulo.toLowerCase());
    if (sel.length === 0) return 'Nada seleccionado';
    return `Se eliminarán: ${sel.join(', ')}.`;
  }

  cancelar(): void {
    if (this.procesando) return;
    this.cerrar.emit();
  }

  eliminar(): void {
    if (!this.haySeleccion || this.procesando) return;
    if (!confirm(`${this.resumen}\n\n¿Continuar?`)) return;

    const body = {
      movimientos: this.opciones.find((o) => o.key === 'movimientos')!.seleccionada,
      cartolas: this.opciones.find((o) => o.key === 'cartolas')!.seleccionada,
      cuentas: this.opciones.find((o) => o.key === 'cuentas')!.seleccionada,
      asociaciones: this.opciones.find((o) => o.key === 'asociaciones')!.seleccionada,
      facturas: this.opciones.find((o) => o.key === 'facturas')!.seleccionada,
    };

    this.procesando = true;
    this.errorMessage = null;

    this.http
      .post(`${this.baseUrl}/limpiar`, body)
      .pipe(finalize(() => (this.procesando = false)))
      .subscribe({
        next: () => this.limpiado.emit(),
        error: (err) => {
          this.errorMessage = err.error?.error ?? err.message;
        },
      });
  }
}