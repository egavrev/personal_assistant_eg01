import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/auth.service';

/** One sidebar entry. `icon` is optional SVG path data on a 24x24 viewBox. */
interface NavItem {
  label: string;
  route: string;
  icon?: string;
}

/**
 * Authenticated app layout: a fixed sidebar (brand, nav, user/logout) beside a
 * scrollable content area driven by the child router outlet.
 *
 * This is the extension seam. Adding a module is two lines and nothing else:
 *   1. one entry in `navItems` below, and
 *   2. one child route under the shell in app.routes.ts.
 */
@Component({
  selector: 'app-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './shell.component.html',
})
export class ShellComponent {
  private readonly auth = inject(AuthService);

  readonly currentUser = this.auth.currentUser;

  readonly navItems: readonly NavItem[] = [
    {
      label: 'Dashboard',
      route: '/',
      icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
    },
    // ADD FUTURE NAV ITEMS HERE — one line each, e.g.:
    // { label: 'Review Queue', route: '/review', icon: '<svg path data>' },
  ];

  logout(): void {
    void this.auth.logout();
  }
}
