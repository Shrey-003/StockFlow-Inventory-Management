
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { of } from 'rxjs';

import { App } from './app';
import { AuthService } from './auth.service';
import { AuthUser } from './auth-state.service';
import { API_BASE_URL } from './api.constants';

describe('Reservation workflows', () => {
  let httpMock: HttpTestingController;

  const testProducts = [
    {
      id: 2,
      name: 'Mechanical Keyboard',
      sku: 'SF-KEYBOARD-001',
      description: 'Mechanical keyboard',
      price: '79.99',
      stock_quantity: 25,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-11-01T10:00:00Z',
    },
    {
      id: 1,
      name: 'Wireless Mouse',
      sku: 'SF-MOUSE-001',
      description: 'Wireless mouse',
      price: '29.99',
      stock_quantity: 3,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-11-01T09:00:00Z',
    },
  ];

  const testReservation = {
    id: 13,
    product_id: 2,
    quantity: 2,
    status: 'active',
    expires_at: '2026-11-01T12:30:00Z',
    created_at: '2026-11-01T12:15:00Z',
    updated_at: '2026-11-01T12:15:00Z',
  };

  function createFixture() {
    const user: AuthUser = {
      id: 2,
      username: 'pranshu',
      role: 'staff',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
    };

    const authMock = {
      currentUser$: of(user),
      currentUser: user,
      restoreSession: () => of(user),
      login: () => of(user),
      logout: () => of(void 0),
    };

    TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: AuthService,
          useValue: authMock,
        },
      ],
    });

    const fixture = TestBed.createComponent(App);
    httpMock = TestBed.inject(HttpTestingController);

    fixture.detectChanges();

    httpMock.expectOne(
      `${API_BASE_URL}/health/db`,
    ).flush({
      status: 'ok',
      service: 'stockflow-api',
    });

    httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'GET',
    ).flush(testProducts);

    fixture.detectChanges();

    return fixture;
  }

  function expectProductAndReservationRefresh(): void {
    const productRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'GET',
    );

    const reservationRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/reservations` &&
        request.method === 'GET',
    );

    productRequest.flush(testProducts);
    reservationRequest.flush([testReservation]);
  }

  afterEach(() => {
    try {
      httpMock.verify();
    } finally {
      vi.restoreAllMocks();
    }
  });

  it('should create a reservation and refresh inventory data', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.showReservations();

    httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/reservations` &&
        request.method === 'GET',
    ).flush([]);

    component.openReservationForm();

    component.reservationForm = {
      product_id: 2,
      quantity: 2,
      ttl_minutes: 15,
    };

    component.createReservation();

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products/2/reservations`,
    );

    expect(request.request.method).toBe('POST');

    expect(request.request.body).toEqual({
      quantity: 2,
      ttl_minutes: 15,
    });

    request.flush(testReservation);

    expect(component.showReservationForm).toBe(false);

    expect(component.reservationSuccess).toContain(
      'Reservation #13 created successfully.',
    );

    expectProductAndReservationRefresh();

    fixture.detectChanges();

    expect(component.reservations.length).toBe(1);
    expect(component.reservations[0].id).toBe(13);
  });

  it('should reject reservation when no product is selected', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.reservationForm = {
      product_id: null,
      quantity: 1,
      ttl_minutes: 15,
    };

    component.createReservation();

    expect(component.reservationError).toBe(
      'Select a product.',
    );

    httpMock.expectNone(
      request => request.url.includes('/reservations'),
    );
  });

  it('should reject zero or invalid reservation quantity', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.reservationForm = {
      product_id: 2,
      quantity: 0,
      ttl_minutes: 15,
    };

    component.createReservation();

    expect(component.reservationError).toBe(
      'Quantity must be a positive whole number.',
    );

    httpMock.expectNone(
      request => request.url.includes('/reservations'),
    );
  });

  it('should reject reservation duration above 120 minutes', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.reservationForm = {
      product_id: 2,
      quantity: 1,
      ttl_minutes: 121,
    };

    component.createReservation();

    expect(component.reservationError).toBe(
      'Expiry must be between 1 and 120 minutes.',
    );

    httpMock.expectNone(
      request => request.url.includes('/reservations'),
    );
  });

  it('should cancel an active reservation and refresh the data', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.showReservations();

    httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/reservations` &&
        request.method === 'GET',
    ).flush([testReservation]);

    vi.spyOn(window, 'confirm').mockReturnValue(true);

    component.cancelReservation(testReservation);

    const request = httpMock.expectOne(
      `${API_BASE_URL}/reservations/13/cancel`,
    );

    expect(request.request.method).toBe('POST');

    request.flush({
      ...testReservation,
      status: 'cancelled',
    });

    expect(component.reservationSuccess).toContain(
      'Reservation #13 cancelled successfully.',
    );

    expectProductAndReservationRefresh();

    fixture.detectChanges();

    expect(component.reservations[0].id).toBe(13);
  });

  it('should not cancel a reservation when confirmation is declined', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    vi.spyOn(window, 'confirm').mockReturnValue(false);

    component.cancelReservation(testReservation);

    httpMock.expectNone(
      `${API_BASE_URL}/reservations/13/cancel`,
    );
  });

  it('should not cancel an already expired reservation', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    const expiredReservation = {
      ...testReservation,
      status: 'expired',
    };

    const confirmSpy = vi.spyOn(window, 'confirm');

    component.cancelReservation(expiredReservation);

    expect(confirmSpy).not.toHaveBeenCalled();

    httpMock.expectNone(
      `${API_BASE_URL}/reservations/13/cancel`,
    );
  });

  it('should handle insufficient stock when reservation creation fails', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.reservationForm = {
      product_id: 2,
      quantity: 100,
      ttl_minutes: 30,
    };

    component.createReservation();

    expect(component.reservationSaving).toBe(true);

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products/2/reservations`,
    );

    expect(request.request.method).toBe('POST');

    request.flush(
      { detail: 'Insufficient stock available.' },
      {
        status: 409,
        statusText: 'Conflict',
      },
    );

    expect(component.reservationSaving).toBe(false);
    expect(component.reservationError).toBe(
      'Insufficient stock available.',
    );
    expect(component.reservationSuccess).toBe('');

    httpMock.expectNone(
      request =>
        request.url === `${API_BASE_URL}/reservations` &&
        request.method === 'GET',
    );
  });

  it('should handle cancellation failure without refreshing reservations', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    vi.spyOn(window, 'confirm').mockReturnValue(true);

    component.cancelReservation(testReservation);

    const request = httpMock.expectOne(
      `${API_BASE_URL}/reservations/13/cancel`,
    );

    expect(request.request.method).toBe('POST');

    request.flush(
      { detail: 'Reservation cannot be cancelled.' },
      {
        status: 409,
        statusText: 'Conflict',
      },
    );

    expect(component.reservationError).toBe(
      'Reservation cannot be cancelled.',
    );
    expect(component.reservationSuccess).toBe('');

    httpMock.expectNone(
      request =>
        request.url === `${API_BASE_URL}/reservations` &&
        request.method === 'GET',
    );
  });

  it('should recover when reservation loading fails temporarily', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.showReservations();

    const failedRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/reservations` &&
        request.method === 'GET',
    );

    failedRequest.flush(
      { detail: 'Reservations service temporarily unavailable.' },
      {
        status: 503,
        statusText: 'Service Unavailable',
      },
    );

    expect(component.reservationsLoading).toBe(false);
    expect(component.reservationError).toBe(
      'Reservations service temporarily unavailable.',
    );

    component.loadReservations();

    const recoveryRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/reservations` &&
        request.method === 'GET',
    );

    recoveryRequest.flush([testReservation]);

    expect(component.reservationsLoading).toBe(false);
    expect(component.reservationError).toBe('');
    expect(component.reservations.length).toBe(1);
    expect(component.reservations[0].id).toBe(
      testReservation.id,
    );
  });

});
