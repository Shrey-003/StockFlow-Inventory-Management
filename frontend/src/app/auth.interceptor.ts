import {
  HttpErrorResponse,
  HttpInterceptorFn,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { API_BASE_URL } from './api.constants';
import { AuthStateService } from './auth-state.service';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const authState = inject(AuthStateService);

  const isLoginRequest =
    request.url === `${API_BASE_URL}/auth/login`;

  const token = authState.accessToken;

  const authenticatedRequest =
    token &&
    request.url.startsWith(`${API_BASE_URL}/`) &&
    !isLoginRequest
      ? request.clone({
          setHeaders: {
            Authorization: `Bearer ${token}`,
          },
        })
      : request;

  return next(authenticatedRequest).pipe(
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        !isLoginRequest
      ) {
        authState.clear();
      }

      return throwError(() => error);
    }),
  );
};
