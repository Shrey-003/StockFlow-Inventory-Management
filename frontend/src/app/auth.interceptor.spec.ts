
import {
  HttpClient,
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http';

import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';

import { TestBed } from '@angular/core/testing';

import { authInterceptor } from './auth.interceptor';
import { AuthStateService, AuthUser } from './auth-state.service';
import { API_BASE_URL } from './api.constants';

describe('AuthInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let authState: AuthStateService;

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
        provideHttpClient(
          withInterceptors([authInterceptor]),
        ),
        provideHttpClientTesting(),
      ],
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    authState = TestBed.inject(AuthStateService);
  });

  afterEach(() => {
    httpMock.verify();
    authState.clear();
  });

  it('should be usable as an HTTP interceptor', () => {
    expect(authState).toBeTruthy();
  });

  it('should attach the bearer token to backend API requests', () => {
    authState.setAccessToken('test-access-token');

    http.get(`${API_BASE_URL}/products`).subscribe();

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products`,
    );

    expect(
      request.request.headers.get('Authorization'),
    ).toBe('Bearer test-access-token');

    request.flush([]);
  });

  it('should not attach authorization when no token exists', () => {
    http.get(`${API_BASE_URL}/products`).subscribe();

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products`,
    );

    expect(
      request.request.headers.has('Authorization'),
    ).toBe(false);

    request.flush([]);
  });

  it('should not attach authorization to login requests', () => {
    authState.setAccessToken('existing-access-token');

    http.post(
      `${API_BASE_URL}/auth/login`,
      {
        username: 'shrey',
        password: 'test-password',
      },
    ).subscribe();

    const request = httpMock.expectOne(
      `${API_BASE_URL}/auth/login`,
    );

    expect(request.request.method).toBe('POST');

    expect(
      request.request.headers.has('Authorization'),
    ).toBe(false);

    request.flush({
      access_token: 'new-access-token',
      token_type: 'bearer',
      expires_in: 1800,
    });
  });

  it('should not attach the token to external URLs', () => {
    authState.setAccessToken('test-access-token');

    http.get('https://example.com/resource').subscribe();

    const request = httpMock.expectOne(
      'https://example.com/resource',
    );

    expect(
      request.request.headers.has('Authorization'),
    ).toBe(false);

    request.flush({});
  });

  it('should clear authentication state when a protected API returns 401', () => {
    authState.setAccessToken('expired-access-token');
    authState.setCurrentUser(testUser);

    http.get(`${API_BASE_URL}/products`).subscribe({
      error: () => undefined,
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products`,
    );

    request.flush(
      { detail: 'Invalid or expired authentication credentials.' },
      {
        status: 401,
        statusText: 'Unauthorized',
      },
    );

    expect(authState.accessToken).toBeNull();
    expect(authState.currentUser).toBeNull();
  });

  it('should not clear the session when login returns 401', () => {
    authState.setAccessToken('existing-access-token');
    authState.setCurrentUser(testUser);

    http.post(
      `${API_BASE_URL}/auth/login`,
      {
        username: 'shrey',
        password: 'incorrect-password',
      },
    ).subscribe({
      error: () => undefined,
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

    expect(authState.accessToken).toBe(
      'existing-access-token',
    );

    expect(authState.currentUser).toEqual(testUser);
  });

  it('should preserve authentication state on HTTP 403', () => {
    authState.setAccessToken('valid-access-token');
    authState.setCurrentUser(testUser);

    http.get(`${API_BASE_URL}/products`).subscribe({
      error: () => undefined,
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products`,
    );

    request.flush(
      { detail: 'Forbidden' },
      {
        status: 403,
        statusText: 'Forbidden',
      },
    );

    expect(authState.accessToken).toBe(
      'valid-access-token',
    );

    expect(authState.currentUser).toEqual(testUser);
  });

  it('should preserve authentication state on HTTP 500', () => {
    authState.setAccessToken('valid-access-token');
    authState.setCurrentUser(testUser);

    http.get(`${API_BASE_URL}/products`).subscribe({
      error: () => undefined,
    });

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products`,
    );

    request.flush(
      { detail: 'Internal Server Error' },
      {
        status: 500,
        statusText: 'Internal Server Error',
      },
    );

    expect(authState.accessToken).toBe(
      'valid-access-token',
    );

    expect(authState.currentUser).toEqual(testUser);
  });
});
