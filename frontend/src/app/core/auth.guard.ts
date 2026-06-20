import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

/**
 * Gate for the authenticated shell. Allows activation when a user is present;
 * otherwise redirects to /login.
 *
 * On a cold load or a direct deep-link the auth state may not be resolved yet
 * (the startup initializer normally settles it first, but this guard does not
 * assume that), so it awaits loadMe() before deciding.
 */
export const authGuard: CanActivateFn = async () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!auth.authChecked()) {
    await auth.loadMe();
  }

  return auth.isAuthenticated() ? true : router.createUrlTree(['/login']);
};
