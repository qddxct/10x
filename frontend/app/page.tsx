import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fetchHealth } from '@/lib/api'

export const dynamic = 'force-dynamic'

export default async function HomePage() {
  let health: { status: string; db: string } | null = null
  let error: string | null = null
  try {
    health = await fetchHealth()
  } catch (err) {
    error = err instanceof Error ? err.message : 'unknown error'
  }

  return (
    <main className="min-h-screen bg-background text-foreground flex items-center justify-center p-8">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-3 text-2xl">
            Sporttery 10x
            <Badge variant="secondary">v0.1.0</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">竞彩交易决策系统 · 项目骨架已就绪。</p>
          <div className="rounded-lg border p-4">
            <div className="text-sm font-medium mb-2">Backend Health</div>
            {error !== null && <Badge variant="destructive">unreachable: {error}</Badge>}
            {health !== null && (
              <div className="flex gap-2">
                <Badge>status: {health.status}</Badge>
                <Badge variant={health.db === 'ok' ? 'default' : 'destructive'}>
                  db: {health.db}
                </Badge>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
