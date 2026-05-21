export type UserRole = 'admin' | 'member'

export interface AuthUser {
  id: number
  phone: string
  name: string
  role: UserRole
}

export interface TokenResponse {
  token: string
  token_type: string
  user: AuthUser
}

export interface LoginRequest {
  phone: string
  password: string
}
