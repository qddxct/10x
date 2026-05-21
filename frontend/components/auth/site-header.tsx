import Link from 'next/link'

import { NavUser } from './nav-user'

export function SiteHeader() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-zinc-800 bg-zinc-950/95 px-6 shadow-[0_10px_40px_rgba(0,0,0,0.22)]">
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold">
          <span className="flex h-7 w-7 items-center justify-center rounded-md border border-amber-500/35 bg-amber-500/10 text-xs text-amber-200">
            S10
          </span>
          <span>Sporttery 10x</span>
        </Link>
        <Link href="/dashboard" className="text-sm text-zinc-400 transition hover:text-amber-200">
          今日推荐
        </Link>
        <Link href="/backtest" className="text-sm text-zinc-400 transition hover:text-amber-200">
          回测
        </Link>
        <Link href="/model" className="text-sm text-zinc-400 transition hover:text-amber-200">
          模型
        </Link>
        <Link href="/review" className="text-sm text-zinc-400 transition hover:text-amber-200">
          复盘
        </Link>
        <Link href="/admin/scrape" className="text-sm text-zinc-400 transition hover:text-amber-200">
          抓取管理
        </Link>
      </div>
      <NavUser />
    </header>
  )
}
