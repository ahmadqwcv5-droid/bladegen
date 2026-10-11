import { useEffect, useMemo, useRef, useState } from 'react'
import { getAirfoilCatalog, getAirfoilProfile, importAirfoil } from '../api/client'
import type { AirfoilCatalogItem, AirfoilProfile } from '../types/bladespec'
import { AirfoilInspector } from './AirfoilInspector'

export function AirfoilSelector({
  stationIndex,
  radius,
  onApply,
  onCancel,
}: {
  stationIndex: number
  radius: number
  onApply: (profile: AirfoilProfile) => void
  onCancel: () => void
}) {
  const [catalog, setCatalog] = useState<AirfoilCatalogItem[]>([])
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<'all' | 'naca4' | 'imported'>('all')
  const [profile, setProfile] = useState<AirfoilProfile>()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [nacaCode, setNacaCode] = useState('0012')
  const [file, setFile] = useState<File>()
  const [displayName, setDisplayName] = useState('')
  const [source, setSource] = useState('')
  const [license, setLicense] = useState('')
  const [notes, setNotes] = useState('')
  const [normalize, setNormalize] = useState(false)
  const selectionRevision = useRef(0)

  const refresh = () => getAirfoilCatalog().then(items => {
    setCatalog(items)
    setLoading(false)
  }).catch(reason => { setError(String(reason)); setLoading(false) })
  useEffect(() => { void refresh() }, [])

  const choose = (id: string) => {
    const revision = ++selectionRevision.current
    setLoading(true)
    setError('')
    getAirfoilProfile(id).then(value => {
      if (revision === selectionRevision.current) setProfile(value)
    }).catch(reason => {
      if (revision === selectionRevision.current) setError(reason instanceof Error ? reason.message : String(reason))
    }).finally(() => {
      if (revision === selectionRevision.current) setLoading(false)
    })
  }

  const visible = useMemo(() => catalog.filter(item => (
    (filter === 'all' || item.category === filter)
    && item.display_name.toLowerCase().includes(query.toLowerCase())
  )), [catalog, filter, query])

  const upload = async () => {
    if (!file) { setError('Choose a DAT or CSV file first'); return }
    setLoading(true)
    setError('')
    try {
      const imported = await importAirfoil(file, {
        displayName: displayName || file.name.replace(/\.[^.]+$/, ''),
        source,
        license,
        notes,
        normalize,
      })
      setProfile(imported)
      await refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="selector-backdrop" role="dialog" aria-modal="true" aria-label={`Airfoil Library for station ${stationIndex + 1}`}>
      <section className="airfoil-selector">
        <div className="section-title">
          <div><p className="eyebrow">AIRFOIL LIBRARY</p><h2>Station {stationIndex + 1} · r/R {radius.toFixed(4)}</h2></div>
          <button onClick={onCancel}>Cancel</button>
        </div>
        <div className="selector-layout">
          <div className="catalog-panel">
            <label>Search profiles<input aria-label="Search airfoils" value={query} onChange={event => setQuery(event.target.value)} /></label>
            <label>Category<select aria-label="Airfoil category" value={filter} onChange={event => setFilter(event.target.value as typeof filter)}><option value="all">All</option><option value="naca4">NACA</option><option value="imported">Imported</option></select></label>
            <div className="catalog-list">{visible.map(item => <button key={item.profile_id} className={profile?.profile_id === item.profile_id ? 'selected' : ''} onClick={() => choose(item.profile_id)}><strong>{item.display_name}</strong><small>{item.category === 'naca4' ? 'Parametric' : item.original_filename}</small></button>)}</div>
            <div className="direct-naca">
              <label>Other NACA 4-digit<input aria-label="Direct NACA code" inputMode="numeric" maxLength={4} value={nacaCode} onChange={event => setNacaCode(event.target.value)} /></label>
              <button disabled={!/^\d{4}$/.test(nacaCode)} onClick={() => choose(`naca-${nacaCode}`)}>Preview NACA</button>
            </div>
            <details className="import-panel">
              <summary>Import DAT or CSV</summary>
              <label>Coordinate file<input aria-label="Airfoil coordinate file" type="file" accept=".dat,.csv,text/plain,text/csv" onChange={event => { const selected = event.target.files?.[0]; setFile(selected); if (selected && !displayName) setDisplayName(selected.name.replace(/\.[^.]+$/, '')) }} /></label>
              <label>Display name<input aria-label="Imported airfoil name" value={displayName} onChange={event => setDisplayName(event.target.value)} /></label>
              <label>Source / provenance<input aria-label="Airfoil source" value={source} onChange={event => setSource(event.target.value)} placeholder="unknown" /></label>
              <label>License<input aria-label="Airfoil license" value={license} onChange={event => setLicense(event.target.value)} placeholder="unknown" /></label>
              <label>Notes<textarea aria-label="Airfoil notes" value={notes} onChange={event => setNotes(event.target.value)} /></label>
              <label className="inline"><input type="checkbox" checked={normalize} onChange={event => setNormalize(event.target.checked)} /> Explicitly normalize using LE and mean TE chord</label>
              <button onClick={() => void upload()}>Import and Preview</button>
            </details>
          </div>
          <div className="selector-preview">
            {loading && <p>Loading canonical profile…</p>}
            {error && <div className="error-panel">{error}</div>}
            {profile && <>
              <AirfoilInspector profile={profile} />
              <dl><dt>Source</dt><dd>{profile.source}</dd><dt>License</dt><dd>{profile.license}</dd>{profile.canonical_coordinate_sha256 && <><dt>Coordinate SHA-256</dt><dd className="checksum">{profile.canonical_coordinate_sha256}</dd></>}</dl>
              {profile.airfoil.type === 'coordinates' && <p className="resolution-note">Applying coordinates the active thickness control at r/R {radius.toFixed(4)} to the profile's natural geometric t/c {profile.metrics.max_thickness_ratio.toFixed(5)}. Other distribution controls are unchanged.</p>}
              <button className="primary" onClick={() => onApply(profile)}>Apply to Station {stationIndex + 1}</button>
            </>}
          </div>
        </div>
      </section>
    </div>
  )
}
