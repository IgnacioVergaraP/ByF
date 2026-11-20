import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { PanelComponent } from './pages/panel/panel.component';
import { MapaComponent } from './pages/mapa/mapa.component';
import { GastosComponent } from './pages/gastos/gastos.component';

const routes: Routes = [
  { path: '', redirectTo: 'ingresos', pathMatch: 'full' },
  { path: 'ingresos', component: PanelComponent },
  { path: 'ingresos/mapa', component: MapaComponent },
  { path: 'gastos', component: GastosComponent },
  { path: 'mapa', redirectTo: 'ingresos/mapa' },
  { path: 'cartolas', redirectTo: 'ingresos' },
  { path: 'conciliaciones', redirectTo: 'ingresos' },
  { path: 'asociaciones', redirectTo: 'ingresos' },
  { path: 'propiedades', redirectTo: 'ingresos' },
  { path: 'historial', redirectTo: 'ingresos' },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class ConciliacionRoutingModule {}