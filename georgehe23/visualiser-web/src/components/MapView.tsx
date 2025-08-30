import { useEffect, useMemo, useRef, useState } from 'react'

type Props = {
  src?: string
  height?: number | string
  className?: string
  autoRefreshMs?: number
}

// Minimal map viewer that embeds a pre-generated HTML map (e.g., Folium output)
// Includes optional polling to auto-reload when the underlying file changes.
export default function MapView({
  src = '../../map/map.html',
  height = '720px',
  className = '',
  autoRefreshMs = 5000,
}: Props) {
  const [displaySrc, setDisplaySrc] = useState(src)
  const lastSig = useRef<string | null>(null)

  // Normalize the base src without cache-busting query
  const baseSrc = useMemo(() => src.split('?')[0], [src])

  useEffect(() => {
    let timer: number | undefined

    const check = async () => {
      try {
        const res = await fetch(baseSrc, { cache: 'no-store' })
        if (!res.ok) return
        const text = await res.text()
        // Avoid embedding the app itself if dev server falls back to index.html
        const looksLikeApp = text.includes('<div id="root">') || text.includes('src="/src/main.tsx"')
        if (looksLikeApp) return

        // Simple signature using length + a small slice
        const sig = `${text.length}:${text.slice(0, 128)}`
        if (lastSig.current === null) {
          lastSig.current = sig
          setDisplaySrc(`${baseSrc}?ts=${Date.now()}`)
        } else if (lastSig.current !== sig) {
          lastSig.current = sig
          setDisplaySrc(`${baseSrc}?ts=${Date.now()}`)
        }
      } catch {
        // ignore network errors in polling
      }
    }

    // Initial check then poll
    check()
    if (autoRefreshMs && autoRefreshMs > 0) {
      // @ts-ignore timers type
      timer = setInterval(check, autoRefreshMs)
    }
    return () => {
      if (timer) clearInterval(timer as unknown as number)
    }
  }, [baseSrc, autoRefreshMs])

  return (
    <div className={`w-full rounded border border-gray-200 overflow-hidden bg-white ${className}`} style={{ height }}>
      <iframe key={displaySrc} src={displaySrc} title="map" className="w-full h-full border-0" />
    </div>
  )
}
