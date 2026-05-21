'use client'

import * as Tooltip from '@radix-ui/react-tooltip'
import styles from './info-tooltip.module.css'

interface InfoTooltipProps {
  text: string
  label?: string
}

export function InfoTooltip({ text, label = '?' }: InfoTooltipProps) {
  return (
    <Tooltip.Provider delayDuration={150}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button type="button" className={styles.trigger} aria-label={text}>
            {label}
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content className={styles.content} sideOffset={4}>
            {text}
            <Tooltip.Arrow className={styles.arrow} />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
