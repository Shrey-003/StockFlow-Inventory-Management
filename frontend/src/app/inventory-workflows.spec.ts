
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

describe('Product management workflows', () => {
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

  function createFixture() {
    const user: AuthUser = {
      id: 1,
      username: 'shrey',
      role: 'admin',
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

  afterEach(() => {
    httpMock.verify();
    vi.restoreAllMocks();
  });

  it('should create a product and refresh the catalog', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.openForm();

    component.form = {
      name: 'Wireless Headphones',
      sku: 'SF-HEADPHONES-001',
      description: 'Bluetooth headphones',
      price: 149.99,
      stock_quantity: 15,
    };

    component.saveProduct();

    const createRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'POST',
    );

    expect(createRequest.request.body).toEqual({
      name: 'Wireless Headphones',
      sku: 'SF-HEADPHONES-001',
      description: 'Bluetooth headphones',
      price: 149.99,
      stock_quantity: 15,
    });

    createRequest.flush({
      ...component.form,
      id: 3,
      created_at: '2026-11-01T12:00:00Z',
      updated_at: '2026-11-01T12:00:00Z',
    });

    const reloadRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'GET',
    );

    reloadRequest.flush([
      ...testProducts,
      {
        id: 3,
        name: 'Wireless Headphones',
        sku: 'SF-HEADPHONES-001',
        description: 'Bluetooth headphones',
        price: '149.99',
        stock_quantity: 15,
        created_at: '2026-11-01T12:00:00Z',
        updated_at: '2026-11-01T12:00:00Z',
      },
    ]);

    fixture.detectChanges();

    expect(component.showForm).toBe(false);
    expect(component.products.length).toBe(3);
    expect(component.successMessage).toContain(
      'Created "Wireless Headphones"',
    );
  });

  it('should reject invalid product data without making an API request', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.openForm();
    component.saveProduct();

    expect(component.errorMessage).toContain(
      'Enter a valid name, SKU, price, and stock quantity.',
    );

    httpMock.expectNone(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'POST',
    );
  });

  it('should update an existing product without resending an unchanged SKU', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    const product = testProducts[0];

    component.editProduct(product);

    component.form.name = 'Updated Mechanical Keyboard';
    component.form.price = 89.99;
    component.form.stock_quantity = 30;

    component.saveProduct();

    const updateRequest = httpMock.expectOne(
      `${API_BASE_URL}/products/${product.id}`,
    );

    expect(updateRequest.request.method).toBe('PATCH');
    expect(updateRequest.request.body.name).toBe(
      'Updated Mechanical Keyboard',
    );
    expect(updateRequest.request.body.price).toBe(89.99);

    expect(
      Object.prototype.hasOwnProperty.call(
        updateRequest.request.body,
        'sku',
      ),
    ).toBe(false);

    updateRequest.flush({
      ...product,
      name: 'Updated Mechanical Keyboard',
      price: '89.99',
      stock_quantity: 30,
    });

    const reloadRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'GET',
    );

    reloadRequest.flush([
      {
        ...product,
        name: 'Updated Mechanical Keyboard',
        price: '89.99',
        stock_quantity: 30,
      },
      testProducts[1],
    ]);

    expect(component.showForm).toBe(false);
    expect(component.successMessage).toContain(
      'Updated "Updated Mechanical Keyboard"',
    );
  });

  it('should delete a product after confirmation', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    vi.spyOn(window, 'confirm').mockReturnValue(true);

    const product = testProducts[0];

    component.deleteProduct(product);

    const deleteRequest = httpMock.expectOne(
      `${API_BASE_URL}/products/${product.id}`,
    );

    expect(deleteRequest.request.method).toBe('DELETE');

    deleteRequest.flush(null);

    const reloadRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'GET',
    );

    reloadRequest.flush([testProducts[1]]);

    expect(component.products.length).toBe(1);
    expect(component.products[0].id).toBe(1);
    expect(component.successMessage).toContain(
      'Deleted "Mechanical Keyboard"',
    );
  });

  it('should not delete a product when confirmation is declined', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    vi.spyOn(window, 'confirm').mockReturnValue(false);

    component.deleteProduct(testProducts[0]);

    httpMock.expectNone(
      `${API_BASE_URL}/products/2`,
    );

    expect(component.products.length).toBe(2);
  });

  it('should display an error and reset saving state when product creation fails', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.openForm();

    component.form = {
      name: 'Duplicate Product',
      sku: 'SF-DUPLICATE-001',
      description: 'Test product',
      price: 50,
      stock_quantity: 10,
    };

    component.saveProduct();

    expect(component.saving).toBe(true);

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products`,
    );

    request.flush(
      { detail: 'A product with this SKU already exists.' },
      {
        status: 409,
        statusText: 'Conflict',
      },
    );

    expect(component.saving).toBe(false);
    expect(component.showForm).toBe(true);
    expect(component.errorMessage).toBe(
      'A product with this SKU already exists.',
    );
    expect(component.successMessage).toBe('');

    httpMock.expectNone(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'GET',
    );
  });

  it('should display an error and reset saving state when product update fails', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.editProduct(testProducts[0]);
    component.form.name = 'Updated Keyboard';

    component.saveProduct();

    expect(component.saving).toBe(true);

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products/2`,
    );

    request.flush(
      { detail: 'Product could not be updated.' },
      {
        status: 500,
        statusText: 'Internal Server Error',
      },
    );

    expect(component.saving).toBe(false);
    expect(component.showForm).toBe(true);
    expect(component.errorMessage).toBe(
      'Product could not be updated.',
    );
  });

  it('should preserve the product and display an error when deletion fails', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    vi.spyOn(window, 'confirm').mockReturnValue(true);

    component.deleteProduct(testProducts[0]);

    const request = httpMock.expectOne(
      `${API_BASE_URL}/products/2`,
    );

    expect(request.request.method).toBe('DELETE');

    request.flush(
      { detail: 'Product cannot be deleted because it has active reservations.' },
      {
        status: 409,
        statusText: 'Conflict',
      },
    );

    expect(component.products.length).toBe(2);
    expect(component.errorMessage).toBe(
      'Product cannot be deleted because it has active reservations.',
    );
    expect(component.successMessage).toBe('');
  });

  it('should recover product loading after an API failure', () => {
    const fixture = createFixture();
    const component = fixture.componentInstance;

    component.loadProducts();

    const failedRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'GET',
    );

    failedRequest.flush(
      { detail: 'Service temporarily unavailable.' },
      {
        status: 503,
        statusText: 'Service Unavailable',
      },
    );

    expect(component.loading).toBe(false);
    expect(component.apiConnected).toBe(false);
    expect(component.errorMessage).toBe(
      'Service temporarily unavailable.',
    );

    component.loadProducts();

    const recoveryRequest = httpMock.expectOne(
      request =>
        request.url === `${API_BASE_URL}/products` &&
        request.method === 'GET',
    );

    recoveryRequest.flush(testProducts);

    expect(component.loading).toBe(false);
    expect(component.apiConnected).toBe(true);
    expect(component.errorMessage).toBe('');
    expect(component.products.length).toBe(2);
  });
});