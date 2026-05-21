import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from '@/components/ui/badge'

describe('Badge component', () => {
  it('renders children text', () => {
    render(<Badge>status: ok</Badge>)
    expect(screen.getByText('status: ok')).toBeInTheDocument()
  })

  it('applies variant class for destructive', () => {
    render(<Badge variant="destructive">down</Badge>)
    const el = screen.getByText('down')
    expect(el.className).toMatch(/destructive/)
  })
})
