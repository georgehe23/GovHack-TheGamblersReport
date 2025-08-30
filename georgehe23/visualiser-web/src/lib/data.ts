import Papa from 'papaparse'
import * as XLSX from 'xlsx'

export type Row = Record<string, any>

export async function parseFile(file: File): Promise<Row[]> {
  const ext = file.name.toLowerCase().split('.').pop()
  if (ext === 'csv') {
    return new Promise((resolve, reject) => {
      Papa.parse<Row>(file, {
        header: true,
        skipEmptyLines: true,
        complete: (res) => resolve(res.data),
        error: (err) => reject(err),
      })
    })
  }
  if (ext === 'xls' || ext === 'xlsx') {
    const buf = await file.arrayBuffer()
    const wb = XLSX.read(buf)
    const sheet = wb.Sheets[wb.SheetNames[0]]
    return XLSX.utils.sheet_to_json<Row>(sheet)
  }
  throw new Error(`Unsupported file type: ${ext}`)
}

export function normalizeName(s: any): string {
  if (s == null) return ''
  const t = String(s).toUpperCase()
  return Array.from(t).filter(ch => /[A-Z0-9 ]/.test(ch)).join('').trim()
}

export function detectLgaColumn(rows: Row[]): string | null {
  if (rows.length === 0) return null
  const candidates = [
    'LGA_NAME','LGA','LGA Name','LGA_NAME_2021','Local Government Area','LG A','lga','lga_name','name','LGA_NAME_2016','AREA_NAME'
  ]
  const cols = Object.keys(rows[0] ?? {})
  for (const c of candidates) if (cols.includes(c)) return c
  for (const c of cols) if (c.toLowerCase().includes('lga')) return c
  return null
}

export function detectValueColumns(rows: Row[]): string[] {
  if (rows.length === 0) return []
  const cols = Object.keys(rows[0])
  const isNumCol = (c: string) => rows.some(r => typeof r[c] === 'number')
  const numeric = cols.filter(isNumCol)
  const priority = numeric.filter(c => /(exp|loss|amount|value|net|total)/i.test(c))
  return priority.length ? priority : numeric.slice(0, 1)
}

export function aggregateByLga(filesRows: Row[][]): { key: string, name: string, metrics: Record<string, number> }[] {
  const map = new Map<string, { name: string, metrics: Record<string, number> }>()
  for (const rows of filesRows) {
    const lgaCol = detectLgaColumn(rows)
    if (!lgaCol) continue
    const valCols = detectValueColumns(rows)
    if (valCols.length === 0) continue
    for (const r of rows) {
      const name = String(r[lgaCol] ?? '').trim()
      if (!name) continue
      const key = normalizeName(name)
      const cur = map.get(key) ?? { name, metrics: {} }
      for (let i = 0; i < valCols.length; i++) {
        const c = valCols[i]
        const k = `metric_${i+1}`
        const v = Number(r[c])
        if (!Number.isFinite(v)) continue
        cur.metrics[k] = (cur.metrics[k] ?? 0) + v
      }
      map.set(key, cur)
    }
  }
  return Array.from(map.entries()).map(([key, v]) => ({ key, name: v.name, metrics: v.metrics }))
}

export type FileMapping = {
  name: string
  rows: Row[]
  lgaCol: string | null
  valueCols: string[]
}

export function aggregateByLgaWithMapping(files: FileMapping[]): { key: string, name: string, metrics: Record<string, number> }[] {
  const map = new Map<string, { name: string, metrics: Record<string, number> }>()
  for (const f of files) {
    if (!f.lgaCol || f.valueCols.length === 0) continue
    for (const r of f.rows) {
      const raw = r[f.lgaCol]
      const name = raw == null ? '' : String(raw).trim()
      if (!name) continue
      const key = normalizeName(name)
      const cur = map.get(key) ?? { name, metrics: {} }
      f.valueCols.forEach((c, idx) => {
        const k = `metric_${idx+1}`
        const v = Number(r[c])
        if (Number.isFinite(v)) cur.metrics[k] = (cur.metrics[k] ?? 0) + v
      })
      map.set(key, cur)
    }
  }
  return Array.from(map.entries()).map(([key, v]) => ({ key, name: v.name, metrics: v.metrics }))
}

export function formatNumber(n: number): string {
  try { return n.toLocaleString(undefined, { maximumFractionDigits: 2 }) } catch { return String(n) }
}

export type Feature = GeoJSON.Feature<GeoJSON.Geometry, any>

export function mergeMetricsIntoGeoJSON(geo: GeoJSON.FeatureCollection, agg: ReturnType<typeof aggregateByLga>) {
  const lookup = new Map(agg.map(a => [a.key, a]))
  const nameFields = ['LGA_NAME','LGA_NAME_2021','LGA_NAME_2016','lga_name','NAME','name','lga']
  let attached = 0
  for (const f of geo.features) {
    const props = (f.properties = f.properties || {})
    let key: string | null = null
    for (const nf of nameFields) {
      if (props[nf]) { key = normalizeName(props[nf]); break }
    }
    if (!key && props['name']) key = normalizeName(props['name'])
    if (!key) continue
    const hit = lookup.get(key)
    if (hit) { Object.assign(props, hit.metrics); attached++ }
  }
  ;(geo as any).properties = { _attached_count: attached, _total_features: geo.features.length }
  return geo
}
