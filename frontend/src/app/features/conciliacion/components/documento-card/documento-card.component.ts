import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-documento-card',
  templateUrl: './documento-card.component.html',
  styleUrls: ['./documento-card.component.scss'],
  standalone: false
})
export class DocumentoCardComponent {
  @Input() icono: string = 'bi-file-earmark-text';
  @Input() titulo: string = '';
  @Input() descripcion: string = '';
  @Input() etiqueta: string | null = null;
  @Input() deshabilitado: boolean = false;
  @Input() acepta: string = '.pdf';

  @Output() fileSelected = new EventEmitter<File>();

  archivoNombre: string | null = null;

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.archivoNombre = file.name;
    this.fileSelected.emit(file);
    input.value = '';
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    if (this.deshabilitado) return;
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    this.archivoNombre = file.name;
    this.fileSelected.emit(file);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
  }
}