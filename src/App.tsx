import { useCallback, useEffect, useMemo, useState } from 'react'
import MapView from './components/MapView'
import { aggregateByLgaWithMapping, mergeMetricsIntoGeoJSON, parseFile, type FileMapping } from './lib/data'

type FC = GeoJSON.FeatureCollection

export default function App() {
  const [basePath, setBasePath] = useState('/data/vic_lga_boundaries.geojson')
  const [baseGeo, setBaseGeo] = useState<FC | null>(null)
  const [fileMaps, setFileMaps] = useState<FileMapping[]>([])
  const [metric, setMetric] = useState<string>('')
  const [enriched, setEnriched] = useState<FC | null>(null)
  const [status, setStatus] = useState<string>('')
  const [mapUrl, setMapUrl] = useState<string | null>(null)

  // Load /georgehe23/map/map.html if present
  useEffect(() => {
    const check = async () => {
      try {
        const url = '/georgehe23/map/map.html'
        const res = await fetch(url)
        if (!res.ok) return
        const text = await res.text()
        const looksLikeIndex = text.includes('<div id="root">') || text.includes('src="/src/main.tsx"')
        if (!looksLikeIndex) setMapUrl(url)
      } catch {}
    }
    check()
  }, [])

  const loadBase = useCallback(async () => {
    setStatus('Loading base GeoJSON…')
    try {
      const res = await fetch(basePath)
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const gj = (await res.json()) as FC
      setBaseGeo(gj)
      setStatus('Loaded base GeoJSON')
    } catch (e: any) {
      setStatus(`Failed to load GeoJSON: ${e.message || e}`)
    }
  }, [basePath])

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return
    setStatus('Parsing uploaded files…')
    const list = Array.from(e.target.files)
    const parsed = await Promise.all(list.map(parseFile))
    const next: FileMapping[] = parsed.map((rows, idx) => {
      const cols = Object.keys(rows[0] || {})
      const lgaGuess = cols.find(c => /lga/i.test(c)) || null
      const numCols = cols.filter(c => rows.some(r => typeof r[c] === 'number'))
      const valueGuess = numCols.filter(c => /(exp|loss|amount|value|net|total)/i.test(c))
      return { name: list[idx].name, rows, lgaCol: lgaGuess, valueCols: valueGuess.length ? valueGuess : (numCols[0] ? [numCols[0]] : []) }
    })
    setFileMaps(next)
    setStatus('Files ready. Review column mapping below.')
  }

  const process = useCallback(async () => {
    if (!baseGeo) { setStatus('Load base GeoJSON first'); return }
    if (!fileMaps.length) { setStatus('Upload and map at least one file'); return }
    setStatus('Aggregating metrics…')
    const agg = aggregateByLgaWithMapping(fileMaps)
    setStatus('Merging metrics into GeoJSON…')
    const merged = mergeMetricsIntoGeoJSON(structuredClone(baseGeo), agg) as FC
    setEnriched(merged)
    const firstMetric = Object.keys(merged?.features?.[0]?.properties || {}).find(k => k.startsWith('metric_')) || ''
    setMetric(firstMetric)
    setStatus('Ready')
  }, [baseGeo, fileMaps])

  const metrics = useMemo(() => {
    const props = enriched?.features?.[0]?.properties || {}
    return Object.keys(props).filter(k => k.startsWith('metric_'))
  }, [enriched])

  const reloadMap = () => setMapUrl(`/georgehe23/map/map.html?ts=${Date.now()}`)

  return (
    <div className="min-h-screen p-4 md:p-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold">Gambling Harm Visualiser (Web)</h1>
        <p className="text-gray-600">Load LGA boundaries, upload gaming expenditure CSV/XLSX, and view an interactive choropleth.</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 space-y-4">
          <div className="p-4 bg-white rounded border">
            <h2 className="font-medium mb-2">Default Map</h2>
            <p className="text-sm text-gray-600">Displays <code>/georgehe23/map/map.html</code> on the right.</p>
            <button className="mt-2 px-3 py-1 bg-blue-600 text-white rounded" onClick={reloadMap}>Show / Update Map</button>
            <div className="text-xs text-gray-500 mt-1">Generate via Python and save to georgehe23/map/map.html</div>
          </div>

          <div className="p-4 bg-white rounded border">
            <h2 className="font-medium mb-2">Base GeoJSON</h2>
            <label className="block text-sm mb-1">Path to GeoJSON</label>
            <input className="w-full border rounded px-2 py-1" value={basePath} onChange={(e) => setBasePath(e.target.value)} />
            <button className="mt-2 px-3 py-1 bg-blue-600 text-white rounded" onClick={loadBase}>Load</button>
            <div className="text-xs text-gray-500 mt-1">Example: /data/vic_lga_boundaries.geojson</div>
          </div>

          <div className="p-4 bg-white rounded border">
            <h2 className="font-medium mb-2">Upload Data</h2>
            <input className="block w-full" type="file" multiple accept=".csv,.xls,.xlsx" onChange={onUpload} />
            <div className="text-xs text-gray-500 mt-1">Accepted: CSV, XLS, XLSX</div>
            <button className="mt-3 px-3 py-1 bg-emerald-600 text-white rounded" onClick={process}>Process & Merge</button>
            <div className="text-xs text-gray-700 mt-2">{status}</div>
          </div>

          {fileMaps.length > 0 && (
            <div className="p-4 bg-white rounded border space-y-3">
              <h2 className="font-medium">Column Mapping</h2>
              <p className="text-sm text-gray-600">Choose the LGA name column and one or more numeric value columns to aggregate.</p>
              {fileMaps.map((fm, idx) => {
                const cols = Object.keys(fm.rows[0] || {})
                return (
                  <div key={fm.name} className="border-t pt-3">
                    <div className="font-medium text-sm mb-2">{fm.name}</div>
                    <label className="block text-xs mb-1">LGA column</label>
                    <select className="w-full border rounded px-2 py-1 mb-2" value={fm.lgaCol ?? ''}
                      onChange={(e) => { const next = [...fileMaps]; next[idx] = { ...fm, lgaCol: e.target.value || null }; setFileMaps(next) }}>
                      <option value="">— select —</option>
                      {cols.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <label className="block text-xs mb-1">Value column(s)</label>
                    <select multiple className="w-full border rounded px-2 py-1 h-28" value={fm.valueCols}
                      onChange={(e) => { const sel = Array.from(e.target.selectedOptions).map(o => o.value); const next = [...fileMaps]; next[idx] = { ...fm, valueCols: sel }; setFileMaps(next) }}>
                      {cols.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="lg:col-span-2">
          <div className="w-full h-[720px] rounded border overflow-hidden bg-white">
            {mapUrl ? (
              <iframe key={mapUrl} src={mapUrl} title="map" className="w-full h-full border-0" />
            ) : (
              <div className="h-full w-full flex items-center justify-center text-gray-500">
                Place a map at /georgehe23/map/map.html then click "Show / Update Map"
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

