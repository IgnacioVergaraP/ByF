import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { MainLayoutComponent } from './layout/main-layout/main-layout.component';

const routes: Routes = [
  {
    path: '',
    component: MainLayoutComponent,
    children: [
      {
        path: 'conciliacion',
        loadChildren: () =>
          import('./features/conciliacion/conciliacion.module').then(
            (m) => m.ConciliacionModule
          )
      },
      {
        path: '',
        redirectTo: 'conciliacion',
        pathMatch: 'full'
      },
      {
        path: '**',
        redirectTo: 'conciliacion'
      }
    ]
  }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule {}