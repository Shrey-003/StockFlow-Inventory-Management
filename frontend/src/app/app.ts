import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, NgZone, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';
import { AuthService } from './auth.service';
import { AuthUser } from './auth-state.service';
import { API_BASE_URL } from './api.constants';

interface Product {
  id: number;
  name: string;
  sku: string;
  description: string | null;
  price: string | number;
  stock_quantity: number;
  created_at: string;
  updated_at: string;
}

interface Reservation {
  id: number;
  product_id: number;
  quantity: number;
  status: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

interface ReservationForm {
  product_id: number | null;
  quantity: number;
  ttl_minutes: number;
}

interface ProductForm {
  name: string;
  sku: string;
  description: string;
  price: number;
  stock_quantity: number;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly zone = inject(NgZone);
  private readonly auth = inject(AuthService);
  private readonly apiUrl = API_BASE_URL;

  authReady = false;
  currentUser: AuthUser | null = null;
  loginUsername = '';
  loginPassword = '';
  loginError = '';
  loginLoading = false;

  get isAdmin(): boolean {
    return this.currentUser?.role === 'admin';
  }

  currentView: 'overview' | 'products' | 'reservations' = 'overview';
  reservations: Reservation[] = [];
  reservationsLoading = false;
  reservationSaving = false;
  showReservationForm = false;
  reservationError = '';
  reservationSuccess = '';
  reservationForm: ReservationForm = {
    product_id: null,
    quantity: 1,
    ttl_minutes: 15,
  };

  products: Product[] = [];
  loading = true;
  saving = false;
  apiConnected = false;
  searchTerm = '';
  showForm = false;
  editingProductId: number | null = null;
  errorMessage = '';
  successMessage = '';

  form: ProductForm = this.emptyForm();

  ngOnInit(): void {
    this.auth.currentUser$.subscribe((user) => {
      this.zone.run(() => {
        const wasAuthenticated = this.currentUser !== null;
        this.currentUser = user;

        if (wasAuthenticated && user === null) {
          this.resetSignedOutState();
        }

        this.cdr.detectChanges();
      });
    });

    this.auth.restoreSession().subscribe((user) => {
      this.zone.run(() => {
        this.currentUser = user;
        this.authReady = true;

        if (user) {
          this.initializeDashboard();
        } else {
          this.loading = false;
        }

        this.cdr.detectChanges();
      });
    });
  }

  private initializeDashboard(): void {
    this.checkHealth();
    this.loadProducts();
  }

  private resetSignedOutState(): void {
    this.products = [];
    this.reservations = [];
    this.loading = false;
    this.reservationsLoading = false;
    this.apiConnected = false;
    this.showForm = false;
    this.showReservationForm = false;
    this.editingProductId = null;
    this.currentView = 'overview';
    this.errorMessage = '';
    this.successMessage = '';
    this.reservationError = '';
    this.reservationSuccess = '';
    this.loginPassword = '';
  }

  login(): void {
    if (this.loginLoading) {
      return;
    }

    const username = this.loginUsername.trim();
    const password = this.loginPassword;

    if (!username || !password) {
      this.loginError = 'Enter your username and password.';
      return;
    }

    this.loginLoading = true;
    this.loginError = '';

    this.auth
      .login(username, password)
      .pipe(
        finalize(() =>
          this.zone.run(() => {
            this.loginLoading = false;
            this.cdr.detectChanges();
          }),
        ),
      )
      .subscribe({
        next: (user) =>
          this.zone.run(() => {
            this.currentUser = user;
            this.loginPassword = '';
            this.loginError = '';
            this.currentView = 'overview';
            this.initializeDashboard();
            this.cdr.detectChanges();
          }),
        error: (error: HttpErrorResponse) =>
          this.zone.run(() => {
            this.loginError =
              error.status === 401 || error.status === 422
                ? 'Invalid username or password.'
                : this.describeError(error);
            this.cdr.detectChanges();
          }),
      });
  }

  logout(): void {
    this.loginPassword = '';
    this.loginError = '';

    this.auth.logout().subscribe({
      error: () => {
        this.zone.run(() => {
          this.loginError =
            'You were signed out locally, but the server could not confirm token revocation. The token may remain valid until it expires.';

          this.cdr.detectChanges();
        });
      },
    });
  }

  get filteredProducts(): Product[] {
    const term = this.searchTerm.trim().toLowerCase();

    if (!term) {
      return this.products;
    }

    return this.products.filter((product) =>
      [product.name, product.sku, product.description ?? ''].some((value) =>
        value.toLowerCase().includes(term),
      ),
    );
  }

  get totalUnits(): number {
    return this.products.reduce((sum, product) => sum + product.stock_quantity, 0);
  }

  get lowStockCount(): number {
    return this.products.filter((product) => product.stock_quantity <= 5).length;
  }

  get inventoryValue(): number {
    return this.products.reduce(
      (sum, product) => sum + Number(product.price) * product.stock_quantity,
      0,
    );
  }

  get attentionProducts(): Product[] {
    return this.products
      .filter((product) => product.stock_quantity <= 5)
      .sort((a, b) => a.stock_quantity - b.stock_quantity);
  }

  get recentlyUpdatedProducts(): Product[] {
    return [...this.products]
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      .slice(0, 5);
  }

  checkHealth(): void {
    this.http.get(`${this.apiUrl}/health/db`).subscribe({
      next: () =>
        this.zone.run(() => {
          this.apiConnected = true;
          this.cdr.detectChanges();
        }),
      error: () =>
        this.zone.run(() => {
          this.apiConnected = false;
          this.cdr.detectChanges();
        }),
    });
  }

  loadProducts(): void {
    this.loading = true;
    this.errorMessage = '';

    this.http
      .get<Product[]>(`${this.apiUrl}/products`, {
        params: { skip: 0, limit: 100 },
      })
      .pipe(
        finalize(() =>
          this.zone.run(() => {
            this.loading = false;
            this.cdr.detectChanges();
          }),
        ),
      )
      .subscribe({
        next: (products) =>
          this.zone.run(() => {
            this.products = [...products].sort((a, b) => b.id - a.id);
            this.apiConnected = true;
            this.cdr.detectChanges();
          }),
        error: (error: HttpErrorResponse) =>
          this.zone.run(() => {
            this.apiConnected = false;
            this.errorMessage = this.describeError(error);
            this.cdr.detectChanges();
          }),
      });
  }

  showOverview(): void {
    this.currentView = 'overview';
  }

  showProducts(): void {
    this.currentView = 'products';
  }

  showReservations(): void {
    this.currentView = 'reservations';
    this.reservationError = '';
    this.reservationSuccess = '';
    this.loadReservations();
  }

  get activeReservationsCount(): number {
    return this.reservations.filter((r) => r.status === 'active').length;
  }

  get cancelledReservationsCount(): number {
    return this.reservations.filter((r) => r.status === 'cancelled').length;
  }

  get expiredReservationsCount(): number {
    return this.reservations.filter((r) => r.status === 'expired').length;
  }

  get selectedReservationProduct(): Product | undefined {
    return this.products.find((p) => p.id === this.reservationForm.product_id);
  }

  productNameForReservation(reservation: Reservation): string {
    const product = this.products.find((p) => p.id === reservation.product_id);
    return product ? product.name : 'Product #' + reservation.product_id;
  }

  reservationStatusClass(status: string): string {
    return status.toLowerCase();
  }

  loadReservations(): void {
    this.reservationsLoading = true;
    this.reservationError = '';

    this.http
      .get<Reservation[]>(this.apiUrl + '/reservations', {
        params: { skip: 0, limit: 100 },
      })
      .pipe(
        finalize(() =>
          this.zone.run(() => {
            this.reservationsLoading = false;
            this.cdr.detectChanges();
          }),
        ),
      )
      .subscribe({
        next: (records) =>
          this.zone.run(() => {
            this.reservations = records;
            this.cdr.detectChanges();
          }),
        error: (error: HttpErrorResponse) =>
          this.zone.run(() => {
            this.reservationError = this.describeError(error);
            this.cdr.detectChanges();
          }),
      });
  }

  refreshReservations(): void {
    this.loadProducts();
    this.loadReservations();
  }

  openReservationForm(): void {
    const available = this.products.find((p) => p.stock_quantity > 0);
    this.reservationForm = {
      product_id: available?.id ?? null,
      quantity: 1,
      ttl_minutes: 15,
    };
    this.reservationError = '';
    this.reservationSuccess = '';
    this.showReservationForm = true;
  }

  closeReservationForm(): void {
    this.showReservationForm = false;
    this.reservationError = '';
  }

  createReservation(): void {
    const form = this.reservationForm;
    if (this.reservationSaving) return;

    if (form.product_id === null || !Number.isInteger(form.product_id)) {
      this.reservationError = 'Select a product.';
      return;
    }

    if (!Number.isInteger(form.quantity) || form.quantity < 1) {
      this.reservationError = 'Quantity must be a positive whole number.';
      return;
    }

    if (!Number.isInteger(form.ttl_minutes) || form.ttl_minutes < 1 || form.ttl_minutes > 120) {
      this.reservationError = 'Expiry must be between 1 and 120 minutes.';
      return;
    }

    this.reservationSaving = true;
    this.reservationError = '';
    this.reservationSuccess = '';

    this.http
      .post<Reservation>(this.apiUrl + '/products/' + form.product_id + '/reservations', {
        quantity: form.quantity,
        ttl_minutes: form.ttl_minutes,
      })
      .pipe(
        finalize(() =>
          this.zone.run(() => {
            this.reservationSaving = false;
            this.cdr.detectChanges();
          }),
        ),
      )
      .subscribe({
        next: (reservation) =>
          this.zone.run(() => {
            this.showReservationForm = false;
            this.reservationSuccess = 'Reservation #' + reservation.id + ' created successfully.';
            this.cdr.detectChanges();
            this.refreshReservations();
          }),
        error: (error: HttpErrorResponse) =>
          this.zone.run(() => {
            this.reservationError = this.describeError(error);
            this.cdr.detectChanges();
          }),
      });
  }

  cancelReservation(reservation: Reservation): void {
    if (reservation.status !== 'active') return;

    if (
      !window.confirm(
        'Cancel reservation #' + reservation.id + '? Its quantity will be returned to inventory.',
      )
    ) {
      return;
    }

    this.reservationError = '';
    this.reservationSuccess = '';

    this.http
      .post<Reservation>(this.apiUrl + '/reservations/' + reservation.id + '/cancel', {})
      .subscribe({
        next: () =>
          this.zone.run(() => {
            this.reservationSuccess = 'Reservation #' + reservation.id + ' cancelled successfully.';
            this.cdr.detectChanges();
            this.refreshReservations();
          }),
        error: (error: HttpErrorResponse) =>
          this.zone.run(() => {
            this.reservationError = this.describeError(error);
            this.cdr.detectChanges();
          }),
      });
  }

  refresh(): void {
    this.checkHealth();
    this.loadProducts();
  }

  openForm(): void {
    this.editingProductId = null;
    this.form = this.emptyForm();
    this.errorMessage = '';
    this.successMessage = '';
    this.showForm = true;
  }

  closeForm(): void {
    this.showForm = false;
    this.editingProductId = null;
    this.errorMessage = '';
  }

  editProduct(product: Product): void {
    this.editingProductId = product.id;
    this.form = {
      name: product.name,
      sku: product.sku,
      description: product.description ?? '',
      price: Number(product.price),
      stock_quantity: product.stock_quantity,
    };
    this.errorMessage = '';
    this.successMessage = '';
    this.showForm = true;
  }

  deleteProduct(product: Product): void {
    if (!window.confirm(`Delete "${product.name}"? This cannot be undone.`)) {
      return;
    }

    this.errorMessage = '';
    this.successMessage = '';

    this.http.delete<void>(`${this.apiUrl}/products/${product.id}`).subscribe({
      next: () =>
        this.zone.run(() => {
          this.successMessage = `Deleted "${product.name}" successfully.`;
          this.cdr.detectChanges();
          this.loadProducts();
        }),
      error: (error: HttpErrorResponse) =>
        this.zone.run(() => {
          this.errorMessage = this.describeError(error);
          this.cdr.detectChanges();
        }),
    });
  }

  saveProduct(): void {
    if (this.saving) {
      return;
    }

    if (
      !this.form.name.trim() ||
      !this.form.sku.trim() ||
      !Number.isFinite(Number(this.form.price)) ||
      Number(this.form.price) < 0 ||
      !Number.isInteger(Number(this.form.stock_quantity)) ||
      Number(this.form.stock_quantity) < 0
    ) {
      this.errorMessage = 'Enter a valid name, SKU, price, and stock quantity.';
      return;
    }

    const payload = {
      name: this.form.name.trim(),
      sku: this.form.sku.trim().toUpperCase(),
      description: this.form.description.trim() || null,
      price: Number(this.form.price),
      stock_quantity: Number(this.form.stock_quantity),
    };

    this.saving = true;
    this.errorMessage = '';
    this.successMessage = '';

    const editingId = this.editingProductId;
    const request =
      editingId === null
        ? this.http.post<Product>(`${this.apiUrl}/products`, payload)
        : this.http.patch<Product>(
            `${this.apiUrl}/products/${editingId}`,
            this.updatePayload(payload, editingId),
          );

    request
      .pipe(
        finalize(() =>
          this.zone.run(() => {
            this.saving = false;
            this.cdr.detectChanges();
          }),
        ),
      )
      .subscribe({
        next: (product) =>
          this.zone.run(() => {
            this.showForm = false;
            this.successMessage =
              editingId === null
                ? `Created "${product.name}" successfully.`
                : `Updated "${product.name}" successfully.`;
            this.editingProductId = null;
            this.cdr.detectChanges();
            this.loadProducts();
          }),
        error: (error: HttpErrorResponse) =>
          this.zone.run(() => {
            this.errorMessage = this.describeError(error);
            this.cdr.detectChanges();
          }),
      });
  }

  stockStatus(product: Product): string {
    if (product.stock_quantity === 0) return 'Out of stock';
    if (product.stock_quantity <= 5) return 'Low stock';
    return 'In stock';
  }

  stockClass(product: Product): string {
    if (product.stock_quantity === 0) return 'out';
    if (product.stock_quantity <= 5) return 'low';
    return 'good';
  }

  private updatePayload(
    payload: {
      name: string;
      sku: string;
      description: string | null;
      price: number;
      stock_quantity: number;
    },
    productId: number,
  ): Record<string, unknown> {
    const update: Record<string, unknown> = { ...payload };
    const current = this.products.find((p) => p.id === productId);

    // Avoid re-sending an unchanged SKU as a duplicate.
    if (current && current.sku === payload.sku) {
      delete update['sku'];
    }

    return update;
  }

  private emptyForm(): ProductForm {
    return {
      name: '',
      sku: '',
      description: '',
      price: 0,
      stock_quantity: 0,
    };
  }

  private describeError(error: HttpErrorResponse): string {
    if (error.status === 0) {
      return 'Cannot reach the API. Check that FastAPI is running and CORS is configured.';
    }

    const detail = error.error?.detail;

    if (typeof detail === 'string') {
      return detail;
    }

    return `Request failed (HTTP ${error.status}). Check the input and try again.`;
  }
}
