
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { App } from './app';
import { AuthService } from './auth.service';
import { AuthUser } from './auth-state.service';
import { API_BASE_URL } from './api.constants';

describe('App', () => {
  let httpMock: HttpTestingController;

  const products = [
    {
      id: 1,
      name: 'Mechanical Keyboard',
      sku: 'SF-KEYBOARD-001',
      description: 'Mechanical keyboard',
      price: '79.99',
      stock_quantity: 25,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-11-01T10:00:00Z',
    },
    {
      id: 2,
      name: 'Wireless Mouse',
      sku: 'SF-MOUSE-001',
      description: 'Wireless mouse',
      price: '29.99',
      stock_quantity: 3,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-11-01T11:00:00Z',
    },
  ];

  function createAuthenticatedFixture(
    role: 'admin' | 'staff',
  ) {
    const user: AuthUser = {
      id: 1,
      username: role === 'admin' ? 'shrey' : 'pranshu',
      role,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
    };

    const authServiceMock = {
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
          useValue: authServiceMock,
        },
      ],
    });

    const fixture = TestBed.createComponent(App);

    httpMock = TestBed.inject(HttpTestingController);

    fixture.detectChanges();

    // Complete dashboard initialization requests.
    httpMock.expectOne(`${API_BASE_URL}/health/db`).flush({
      status: 'ok',
      service: 'stockflow-api',
    });

    httpMock.expectOne(
      request => request.url === `${API_BASE_URL}/products`,
    ).flush(products);

    fixture.detectChanges();

    return fixture;
  }

  function navigateTo(
    fixture: ReturnType<typeof TestBed.createComponent<App>>,
    label: string,
  ): void {
    const navItems = fixture.nativeElement.querySelectorAll(
      '.nav-item',
    ) as NodeListOf<HTMLElement>;

    const item = Array.from(navItems).find(
      element => element.textContent?.includes(label),
    );

    expect(item).toBeTruthy();

    item?.click();

    fixture.detectChanges();
  }

  afterEach(() => {
    httpMock.verify();
  });

  it('should create the app', () => {
    const fixture = createAuthenticatedFixture('admin');

    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should display the inventory overview dashboard', () => {
    const fixture = createAuthenticatedFixture('staff');
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('h1')?.textContent)
      .toContain('Inventory overview');

    expect(element.textContent).toContain('Stock health');
    expect(element.textContent).toContain('Recently updated products');

    expect(element.querySelector('.stats')).toBeTruthy();

    // The overview must not display the product search toolbar.
    expect(
      element.querySelector('.toolbar input[type="search"]'),
    ).toBeNull();
  });

  it('should display a separate product catalog', () => {
    const fixture = createAuthenticatedFixture('staff');

    navigateTo(fixture, 'Product catalog');

    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('h1')?.textContent)
      .toContain('Product catalog');

    expect(element.textContent).toContain('All products');

    expect(
      element.querySelector('.toolbar input[type="search"]'),
    ).toBeTruthy();

    // Product catalog should not contain dashboard KPI cards.
    expect(element.querySelector('.stats')).toBeNull();

    expect(element.textContent).toContain('Mechanical Keyboard');
    expect(element.textContent).toContain('Wireless Mouse');
  });

  it('should mark the selected navigation item as active', () => {
    const fixture = createAuthenticatedFixture('staff');

    navigateTo(fixture, 'Product catalog');

    const navItems = fixture.nativeElement.querySelectorAll(
      '.nav-item',
    ) as NodeListOf<HTMLElement>;

    const activeItem = Array.from(navItems).find(
      element => element.classList.contains('active'),
    );

    expect(activeItem?.textContent).toContain('Product catalog');

    navigateTo(fixture, 'Inventory overview');

    const updatedActiveItem = Array.from(navItems).find(
      element => element.classList.contains('active'),
    );

    expect(updatedActiveItem?.textContent)
      .toContain('Inventory overview');
  });

  it('should display the separate reservations interface', () => {
    const fixture = createAuthenticatedFixture('staff');

    navigateTo(fixture, 'Reservations');

    httpMock.expectOne(
      request => request.url === `${API_BASE_URL}/reservations`,
    ).flush([]);

    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('h1')?.textContent)
      .toContain('Reservations');

    expect(element.querySelector('.reservation-stats'))
      .toBeTruthy();

    expect(element.querySelector('.reservation-table-card'))
      .toBeTruthy();

    expect(element.querySelector('.stats')).toBeNull();
  });

  it('should hide product management actions from staff', () => {
    const fixture = createAuthenticatedFixture('staff');

    navigateTo(fixture, 'Product catalog');

    const element = fixture.nativeElement as HTMLElement;

    // Staff must not see the Add product button.
    expect(
      element.querySelector('.top-actions .btn.primary'),
    ).toBeNull();

    // Staff must not see the Actions table column.
    const headers = Array.from(
      element.querySelectorAll('th'),
    );

    expect(
      headers.some(header =>
        header.textContent?.trim() === 'ACTIONS',
      ),
    ).toBe(false);

    // Staff must not see Edit or Delete buttons.
    expect(
      element.querySelectorAll('.row-actions button').length,
    ).toBe(0);
  });

  it('should display product management actions to admin', () => {
    const fixture = createAuthenticatedFixture('admin');

    navigateTo(fixture, 'Product catalog');

    const element = fixture.nativeElement as HTMLElement;

    expect(
      element.querySelector('.top-actions .btn.primary')?.textContent,
    ).toContain('Add product');

    const headers = Array.from(
      element.querySelectorAll('th'),
    );

    expect(
      headers.some(header =>
        header.textContent?.trim() === 'ACTIONS',
      ),
    ).toBe(true);

    expect(
      element.querySelectorAll('.row-actions button').length,
    ).toBe(4);
  });
});
