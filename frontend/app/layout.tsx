import type { Metadata } from 'next'
import { Inter } from 'next/font/google'

import { AuthHydrator } from '@/components/auth/auth-hydrator'
import { SiteHeader } from '@/components/auth/site-header'

import './globals.css'

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' })

export const metadata: Metadata = {
  title: 'Sporttery 10x',
  description: '平让平竞彩交易系统'
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className="dark">
      <body
        className={`${inter.variable} font-sans antialiased min-h-screen bg-background text-foreground`}
      >
        <AuthHydrator />
        <SiteHeader />
        {children}
      </body>
    </html>
  )
}
