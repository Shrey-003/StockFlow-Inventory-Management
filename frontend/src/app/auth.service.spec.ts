
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthService } from './auth.service';
import { AuthStateService, AuthUser } from './auth-state.service';
import { API_BASE_URL } from './api.constants';

describe('AuthService', () => {
  let service: AuthService;
  let authState: AuthStateService;
  let httpMock: HttpTestingController;

  const testUser: AuthUser = {
    id: 1,
    username: 'shrey',
    role: 'admin',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
  };

  beforeEach(() => {
    sessionStorage.removeItem('stockflow_access_token');

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(AuthService);
    authState = TestBed.inject(AuthStateService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    authState.clear();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should return null without making an API request when no token exists', () => {
    let result: AuthUser | null | undefined;

    service.restoreSession().subscribe(user => {
      result = user;
    });

    expect(result).toBeNull();

    httpMock.expectNone(`${API_BASE_URL}/auth/me`);
  });

  it('should restore a valid session', () => {
    authState.setAccessToken('saved-access-token');

    let result: AuthUser | null | undefined;

    service.restoreSession().subscribe(user => {
      result = user;
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/auth/me`,
    );

    expect(request.request.method).toBe('GET');

    request.flush(testUser);

    expect(result).toEqual(testUser);
    expect(authState.currentUser).toEqual(testUser);
    expect(authState.accessToken).toBe('saved-access-token');
  });

  it('should clear the token when session restoration returns 401', () => {
    authState.setAccessToken('invalid-token');

    let result: AuthUser | null | undefined;

    service.restoreSession().subscribe(user => {
      result = user;
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/auth/me`,
    );

    request.flush(
      { detail: 'Invalid or expired authentication credentials.' },
      {
        status: 401,
        statusText: 'Unauthorized',
      },
    );

    expect(result).toBeNull();
    expect(authState.accessToken).toBeNull();
    expect(authState.currentUser).toBeNull();
  });

  it('should preserve the token during a temporary network failure', () => {
    authState.setAccessToken('saved-access-token');

    let result: AuthUser | null | undefined;

    service.restoreSession().subscribe(user => {
      result = user;
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/auth/me`,
    );

    request.error(new ProgressEvent('error'));

    expect(result).toBeNull();
    expect(authState.accessToken).toBe('saved-access-token');
    expect(authState.currentUser).toBeNull();
  });

  it('should login, save the token and load the current user', () => {
    let result: AuthUser | null | undefined;

    service.login('  SHREY  ', 'TestPassword123!').subscribe(user => {
      result = user;
    });

    const loginRequest = httpMock.expectOne(
      `${API_BASE_URL}/auth/login`,
    );

    expect(loginRequest.request.method).toBe('POST');
    expect(loginRequest.request.body).toEqual({
      username: 'shrey',
      password: 'TestPassword123!',
    });

    loginRequest.flush({
      access_token: 'new-access-token',
      token_type: 'bearer',
      expires_in: 1800,
    });

    expect(authState.accessToken).toBe('new-access-token');

    const userRequest = httpMock.expectOne(
      `${API_BASE_URL}/auth/me`,
    );

    expect(userRequest.request.method).toBe('GET');

    userRequest.flush(testUser);

    expect(result).toEqual(testUser);
    expect(authState.currentUser).toEqual(testUser);
  });

  it('should clear authentication state when login fails', () => {
    authState.setAccessToken('previous-token');
    authState.setCurrentUser(testUser);

    let receivedError = false;

    service.login('shrey', 'IncorrectPassword123!').subscribe({
      error: () => {
        receivedError = true;
      },
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/auth/login`,
    );

    request.flush(
      { detail: 'Incorrect username or password.' },
      {
        status: 401,
        statusText: 'Unauthorized',
      },
    );

    expect(receivedError).toBe(true);
    expect(authState.accessToken).toBeNull();
    expect(authState.currentUser).toBeNull();
  });

  it('should revoke the backend session and clear local state on logout', () => {
    authState.setAccessToken('active-access-token');
    authState.setCurrentUser(testUser);

    let completed = false;

    service.logout().subscribe({
      next: () => {
        completed = true;
      },
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/auth/logout`,
    );

    expect(request.request.method).toBe('POST');
    expect(request.request.body).toBeNull();

    request.flush(null, {
      status: 204,
      statusText: 'No Content',
    });

    expect(completed).toBe(true);
    expect(authState.accessToken).toBeNull();
    expect(authState.currentUser).toBeNull();
  });

  it('should complete local logout when backend returns 401', () => {
    authState.setAccessToken('already-revoked-token');
    authState.setCurrentUser(testUser);

    let completed = false;
    let receivedError = false;

    service.logout().subscribe({
      next: () => {
        completed = true;
      },
      error: () => {
        receivedError = true;
      },
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/auth/logout`,
    );

    request.flush(
      { detail: 'Invalid or expired authentication credentials.' },
      {
        status: 401,
        statusText: 'Unauthorized',
      },
    );

    expect(completed).toBe(true);
    expect(receivedError).toBe(false);
    expect(authState.accessToken).toBeNull();
    expect(authState.currentUser).toBeNull();
  });

  it('should clear local state and report network failure during logout', () => {
    authState.setAccessToken('active-access-token');
    authState.setCurrentUser(testUser);

    let receivedError = false;

    service.logout().subscribe({
      error: () => {
        receivedError = true;
      },
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/auth/logout`,
    );

    request.error(new ProgressEvent('error'));

    expect(receivedError).toBe(true);
    expect(authState.accessToken).toBeNull();
    expect(authState.currentUser).toBeNull();
  });
});
