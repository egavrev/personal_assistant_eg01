import { computed, inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

/** The authenticated owner, as returned by GET /api/auth/me. */
export interface User {
  email: string;
}

/**
 * Single source of truth for auth state.
 *
 * The backend owns the session (an HttpOnly cookie); this service never stores
 * tokens. It only mirrors "are we logged in, and as whom" into signals so the
 * router, guard, and UI can react.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  private readonly _currentUser = signal<User | null>(null);
  /** The signed-in owner, or null when not authenticated. */
  readonly currentUser = this._currentUser.asReadonly();
  /** Derived: true when a user is present. */
  readonly isAuthenticated = computed(() => this._currentUser() !== null);

  private readonly _authChecked = signal(false);
  /** True once the first loadMe() has resolved, so guards know state is settled. */
  readonly authChecked = this._authChecked.asReadonly();

  /**
   * Ask the backend who we are. 200 -> set currentUser; 401 (or any transport
   * error) -> clear it. Idempotent; always flips authChecked so callers can
   * await a definitive answer. Called once at startup via an app initializer.
   */
  async loadMe(): Promise<void> {
    try {
      const user = await firstValueFrom(this.http.get<User>('/api/auth/me'));
      this._currentUser.set(user);
    } catch {
      this._currentUser.set(null);
    } finally {
      this._authChecked.set(true);
    }
  }

  /**
   * Begin Google login. This is a full-page navigation, NOT an HttpClient call:
   * OAuth requires a real top-level browser redirect to Google's consent screen.
   * The backend handles the whole exchange and redirects back to the app.
   */
  login(): void {
    window.location.href = '/api/auth/login';
  }

  /** Clear the backend session, drop local state, and return to the login screen. */
  async logout(): Promise<void> {
    try {
      await firstValueFrom(this.http.get('/api/auth/logout'));
    } finally {
      this._currentUser.set(null);
      await this.router.navigate(['/login']);
    }
  }
}
