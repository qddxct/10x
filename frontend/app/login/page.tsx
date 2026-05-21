import { LoginForm } from './login-form'

export const dynamic = 'force-dynamic'

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
      <LoginForm />
    </main>
  )
}
