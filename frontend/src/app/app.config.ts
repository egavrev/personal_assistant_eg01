import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';

import { routes } from './app.routes';
import { credentialsInterceptor } from './core/credentials.interceptor';
import { AuthService } from './core/auth.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withFetch(), withInterceptors([credentialsInterceptor])),
    // Resolve the session before the app renders, so the first navigation
    // already knows whether we're authenticated (no flash of the login screen
    // for a logged-in user, and the guard has a settled answer).
    provideAppInitializer(() => inject(AuthService).loadMe()),
  ],
};
