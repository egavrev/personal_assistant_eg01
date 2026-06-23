/** One sidebar entry. `icon` is optional SVG path data on a 24x24 viewBox. */
export interface NavItem {
  label: string;
  route: string;
  icon?: string;
}

/**
 * The sidebar menu, in render order — the dashboard's extension seam.
 *
 * Adding a module is exactly two lines and nothing else:
 *   1. one entry in this array, and
 *   2. one matching child route under the shell in app.routes.ts.
 * The ShellComponent renders this array in a loop with routerLinkActive.
 */
export const NAV_ITEMS: readonly NavItem[] = [
  {
    label: 'Dashboard',
    route: '/',
    icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
  },
  // FUTURE MODULES GO HERE — one line each, paired with a child route in
  // app.routes.ts. e.g.:
  // { label: 'Review Queue', route: '/review', icon: '<svg path data>' },
  // { label: 'Browse Mail', route: '/signals', icon: '<svg path data>' },
];
