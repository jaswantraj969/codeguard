import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'

export interface TabDefinition {
  id: string
  label: ReactNode
  panel: ReactNode
}

interface TabsProps {
  label: string
  tabs: TabDefinition[]
  initialTab?: string
}

/**
 * WAI-ARIA tabs: arrow keys, Home and End move between tabs; Tab moves into the panel.
 * Remount with a new `key` to reset the selected tab.
 */
export default function Tabs({ label, tabs, initialTab }: TabsProps) {
  const baseId = useId()
  const [selected, setSelected] = useState(initialTab ?? tabs[0]?.id)
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const selectedIndex = Math.max(
    0,
    tabs.findIndex((tab) => tab.id === selected),
  )

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const last = tabs.length - 1
    const next =
      event.key === 'ArrowRight'
        ? selectedIndex === last ? 0 : selectedIndex + 1
        : event.key === 'ArrowLeft'
          ? selectedIndex === 0 ? last : selectedIndex - 1
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : null
    if (next === null) return
    event.preventDefault()
    setSelected(tabs[next].id)
    tabRefs.current[next]?.focus()
  }

  return (
    <div className="tabs">
      <div role="tablist" aria-label={label} className="tablist" onKeyDown={onKeyDown}>
        {tabs.map((tab, index) => {
          const isSelected = index === selectedIndex
          return (
            <button
              key={tab.id}
              ref={(element) => {
                tabRefs.current[index] = element
              }}
              type="button"
              role="tab"
              id={`${baseId}-tab-${tab.id}`}
              aria-selected={isSelected}
              aria-controls={`${baseId}-panel-${tab.id}`}
              tabIndex={isSelected ? 0 : -1}
              className="tab"
              onClick={() => setSelected(tab.id)}
            >
              {tab.label}
            </button>
          )
        })}
      </div>
      {tabs.map((tab, index) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`${baseId}-panel-${tab.id}`}
          aria-labelledby={`${baseId}-tab-${tab.id}`}
          hidden={index !== selectedIndex}
          tabIndex={0}
          className="tabpanel"
        >
          {index === selectedIndex && tab.panel}
        </div>
      ))}
    </div>
  )
}
