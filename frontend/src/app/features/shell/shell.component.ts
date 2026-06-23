import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { NAV_ITEMS } from '../../core/nav';

/**
 * Authenticated app layout: a fixed sidebar (brand, nav, user/logout) beside a
 * scrollable content area driven by the child router outlet.
 *
 * The menu itself is defined once in `core/nav.ts` (the extension seam); the
 * shell just renders it. Adding a module is one entry there + one child route
 * in app.routes.ts.
 */
@Component({
  selector: 'app-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './shell.component.html',
})
export class ShellComponent {
  private readonly auth = inject(AuthService);

  readonly currentUser = this.auth.currentUser;
  /** Sidebar menu, defined once in core/nav.ts. */
  readonly navItems = NAV_ITEMS;

  logout(): void {
    void this.auth.logout();
  }
}
