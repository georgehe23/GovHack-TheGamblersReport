type Props = {
  src?: string
  height?: number | string
  className?: string
}

// Root-level app: serve the Folium map from /georgehe23/map/map.html
export default function MapView({ src = '/georgehe23/map/map.html', height = '720px', className = '' }: Props) {
  return (
    <div className={`w-full rounded border border-gray-200 overflow-hidden bg-white ${className}`} style={{ height }}>
      <iframe key={src} src={src} title="map" className="w-full h-full border-0" />
    </div>
  )
}

