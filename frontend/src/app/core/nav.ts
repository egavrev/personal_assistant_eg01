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
  {
    label: 'Review Queue',
    route: '/review',
    icon: 'M20 3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM10 17H5v-2h5v2zm0-4H5v-2h5v2zm0-4H5V7h5v2zm4.82 6L12 12.16l1.41-1.41 1.41 1.42L17.99 9l1.42 1.42L14.82 15z',
  },
  {
    label: 'Browse Mail',
    route: '/signals',
    icon: 'M15.5 14h-.79l-.28-.27a6.5 6.5 0 1 0-.7.7l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z',
  },
  // FUTURE MODULES GO HERE — one line each, paired with a child route in
  // app.routes.ts.
];
