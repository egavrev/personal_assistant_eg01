import { HttpInterceptorFn } from '@angular/common/http';

/**
 * Attach the backend session cookie to every request.
 *
 * The session cookie is HttpOnly, so JavaScript can neither read nor set it;
 * the browser only sends it when the request opts in via `withCredentials`.
 * Centralising that here means no call site can forget it and silently lose
 * authentication.
 */
export const credentialsInterceptor: HttpInterceptorFn = (req, next) =>
  next(req.clone({ withCredentials: true }));
