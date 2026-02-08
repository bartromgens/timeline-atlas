import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly isLoggedInSubject = new BehaviorSubject<boolean>(false);
  readonly isLoggedIn$: Observable<boolean> = this.isLoggedInSubject.asObservable();

  constructor(private http: HttpClient) {}

  checkAuth(): void {
    this.http.get('/api/auth/me/', { withCredentials: true, responseType: 'text' }).subscribe({
      next: () => this.isLoggedInSubject.next(true),
      error: () => this.isLoggedInSubject.next(false),
    });
  }
}
