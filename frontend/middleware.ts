import { NextResponse, type NextRequest } from 'next/server'

const TOKEN_COOKIE = 'sporttery_token'
const PUBLIC_PATHS = ['/login']

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))
}

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl
  const token = req.cookies.get(TOKEN_COOKIE)?.value

  if (isPublic(pathname)) {
    return NextResponse.next()
  }

  if (!token) {
    const loginUrl = new URL('/login', req.url)
    loginUrl.searchParams.set('redirect', `${pathname}${search}`)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api/|assets/|public/).*)']
}
