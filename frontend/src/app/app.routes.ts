import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';
import { LoginComponent } from './features/login/login.component';
import { ShellComponent } from './features/shell/shell.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';

export const routes: Routes = [
  // Public: the login screen.
  { path: 'login', component: LoginComponent },

  // Authenticated app. The guard protects the shell and, by inheritance, every
  // child page below it.
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', component: DashboardComponent },
      // ADD FUTURE PAGES HERE — one line each, paired with a navItems entry in
      // shell.component.ts, e.g.:
      // { path: 'review', component: ReviewQueueComponent },
    ],
  },

  // Anything unknown falls back into the guarded app (which bounces to /login
  // when unauthenticated).
  { path: '**', redirectTo: '' },
];
