import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
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
      catchError(() => {
        this.authState.clear();
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

  logout(): void {
    this.authState.clear();
  }
}
