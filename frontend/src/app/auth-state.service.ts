import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

export interface AuthUser {
  id: number;
  username: string;
  role: 'admin' | 'staff';
  is_active: boolean;
  created_at: string;
}

@Injectable({
  providedIn: 'root',
})
export class AuthStateService {
  private readonly tokenKey = 'stockflow_access_token';
  private fallbackToken: string | null = null;

  private readonly userSubject =
    new BehaviorSubject<AuthUser | null>(null);

  readonly currentUser$ = this.userSubject.asObservable();

  get currentUser(): AuthUser | null {
    return this.userSubject.value;
  }

  get accessToken(): string | null {
    try {
      return typeof sessionStorage !== 'undefined'
        ? sessionStorage.getItem(this.tokenKey)
        : this.fallbackToken;
    } catch {
      return this.fallbackToken;
    }
  }

  setAccessToken(token: string): void {
    this.fallbackToken = token;

    try {
      sessionStorage.setItem(this.tokenKey, token);
    } catch {
      // Retain the token in memory for this application session.
    }
  }

  setCurrentUser(user: AuthUser): void {
    this.userSubject.next(user);
  }

  clear(): void {
    this.fallbackToken = null;

    try {
      sessionStorage.removeItem(this.tokenKey);
    } catch {
      // Continue clearing the in-memory session.
    }

    this.userSubject.next(null);
  }
}
