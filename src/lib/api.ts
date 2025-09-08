import { User } from '@/types/user'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-b52f.up.railway.app'

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    
    const config: RequestInit = {
      headers: {
        // Don't set Content-Type for FormData - let browser handle it
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
      credentials: 'include', // Important: include cookies in requests
      ...options,
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        console.error('API Error:', response.status, response.statusText, errorData)
        
        // Handle detailed error messages properly
        let errorMessage = `HTTP error! status: ${response.status}`
        if (errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map((err: any) => 
              typeof err === 'object' ? JSON.stringify(err) : err
            ).join(', ')
          } else {
            errorMessage = errorData.detail
          }
        } else if (errorData.message) {
          errorMessage = errorData.message
        }
        
        throw new Error(errorMessage)
      }

      return await response.json()
    } catch (error) {
      throw error
    }
  }

  // Auth methods
  async register(email: string, password: string) {
    return this.request('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  }

  async login(email: string, password: string) {
    return this.request('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  }

  async logout() {
    return this.request('/api/v1/auth/logout', {
      method: 'POST',
    })
  }

  async getCurrentUser(): Promise<User> {
    return this.request<User>('/api/v1/auth/me')
  }

  async refreshToken() {
    return this.request('/api/v1/auth/refresh', {
      method: 'POST',
    })
  }

  // Property methods
  async getProperties() {
    return this.request('/api/v1/properties/', { method: 'GET' })
  }

  async getProperty(id: number) {
    return this.request(`/api/v1/properties/${id}`, { method: 'GET' })
  }

  async createProperty(propertyData: any) {
    return this.request('/api/v1/properties/', {
      method: 'POST',
      body: JSON.stringify(propertyData),
    })
  }

  async updateProperty(id: number, propertyData: any) {
    return this.request(`/api/v1/properties/${id}`, {
      method: 'PUT',
      body: JSON.stringify(propertyData),
    })
  }

  async deleteProperty(id: number) {
    return this.request(`/api/v1/properties/${id}`, { method: 'DELETE' })
  }

  // Quota methods
  async getUserQuota() {
    return this.request<any>('/api/v1/users/quota', { method: 'GET' })
  }

  // Generic methods for future use
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async put<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }
}

export const api = new ApiClient(API_BASE_URL)