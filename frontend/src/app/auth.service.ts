
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import {
  Observable,
  catchError,
  of,
  switchMap,
  tap,
  throwError,
} from 'rxjs';

import { API_BASE_URL } from './api.constants';
import { AuthStateService, AuthUser } from './auth-state.service';

interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly authState = inject(AuthStateService);

  get currentUser(): AuthUser | null {
    return this.authState.currentUser;
  }

  get currentUser$(): Observable<AuthUser | null> {
    return this.authState.currentUser$;
  }

  restoreSession(): Observable<AuthUser | null> {
    if (!this.authState.accessToken) {
      this.authState.clear();
      return of(null);
    }

    return this.http.get<AuthUser>(`${API_BASE_URL}/auth/me`).pipe(
      tap(user => this.authState.setCurrentUser(user)),
      catchError((error: unknown) => {
        // A 401 means the token is invalid, expired, or revoked.
        if (
          error instanceof HttpErrorResponse &&
          error.status === 401
        ) {
          this.authState.clear();
        }

        // Preserve the saved token during temporary network or server
        // failures so session restoration can be retried later.
        return of(null);
      }),
    );
  }

  login(username: string, password: string): Observable<AuthUser> {
    return this.http.post<LoginResponse>(
      `${API_BASE_URL}/auth/login`,
      {
        username: username.trim().toLowerCase(),
        password,
      },
    ).pipe(
      tap(response => {
        this.authState.setAccessToken(response.access_token);
      }),
      switchMap(() =>
        this.http.get<AuthUser>(`${API_BASE_URL}/auth/me`),
      ),
      tap(user => {
        this.authState.setCurrentUser(user);
      }),
      catchError(error => {
        this.authState.clear();
        return throwError(() => error);
      }),
    );
  }

  logout(): Observable<void> {
    const token = this.authState.accessToken;

    if (!token) {
      this.authState.clear();
      return of(void 0);
    }

    return this.http.post<void>(
      `${API_BASE_URL}/auth/logout`,
      null,
    ).pipe(
      tap(() => {
        this.authState.clear();
      }),
      catchError((error: unknown) => {
        // Always end the local session, even when the API is unavailable.
        this.authState.clear();

        // An already-invalid or revoked token is effectively logged out.
        if (
          error instanceof HttpErrorResponse &&
          error.status === 401
        ) {
          return of(void 0);
        }

        // Preserve the error so the UI can inform the user that
        // server-side revocation could not be confirmed.
        return throwError(() => error);
      }),
    );
  }
}
