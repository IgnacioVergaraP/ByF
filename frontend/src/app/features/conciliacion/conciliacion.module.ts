import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';

import { ConciliacionRoutingModule } from './conciliacion-routing.module';
import { PanelComponent } from './pages/panel/panel.component';
import { MapaComponent } from './pages/mapa/mapa.component';
import { DocumentoCardComponent } from './components/documento-card/documento-card.component';
import { AdministrarPropiedadesComponent } from './components/administrar-propiedades/administrar-propiedades.component';
import { AsociarMovimientoComponent } from './components/asociar-movimiento/asociar-movimiento.component';
import { MapaTarjetasComponent } from './components/mapa-tarjetas/mapa-tarjetas.component';
import { MapaTablaComponent } from './components/mapa-tabla/mapa-tabla.component';
import { LimpiarModalComponent } from './components/limpiar-modal/limpiar-modal.component';
import { FacturasPanelComponent } from './components/facturas-panel/facturas-panel.component';
import { AsociarFacturaComponent } from './components/asociar-factura/asociar-factura.component';
import { AplicarPagoComponent } from './components/aplicar-pago/aplicar-pago.component';
import { FacturaAplicacionesComponent } from './components/factura-aplicaciones/factura-aplicaciones.component';
import { GastosComponent } from './pages/gastos/gastos.component';

@NgModule({
  declarations: [
    PanelComponent, MapaComponent, GastosComponent, DocumentoCardComponent,
    AdministrarPropiedadesComponent, AsociarMovimientoComponent,
    MapaTarjetasComponent, MapaTablaComponent, LimpiarModalComponent,
    FacturasPanelComponent, AsociarFacturaComponent,
    AplicarPagoComponent, FacturaAplicacionesComponent,
  ],
  imports: [
    CommonModule, HttpClientModule, ReactiveFormsModule, FormsModule,
    ConciliacionRoutingModule,
  ]
})
export class ConciliacionModule {}