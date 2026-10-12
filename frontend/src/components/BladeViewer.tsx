import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import {
  calculateCameraFrame,
  deriveBladeViewDirections,
  radialUp,
  type BladeViewDirections,
} from './bladeViewerCamera'
import {
  createStationGuideGroup,
  disposeStationGuideGroup,
  type StationGuide,
} from './stationGuides'

type ViewMode = 'face' | 'edge' | 'isometric'

type ViewActions = {
  fit: () => void
  face: () => void
  edge: () => void
  isometric: () => void
}

const emptyActions = (): ViewActions => ({
  fit: () => undefined,
  face: () => undefined,
  edge: () => undefined,
  isometric: () => undefined,
})

const defaultDirections = (): BladeViewDirections => ({
  face: new THREE.Vector3(0, 0, 1),
  edge: new THREE.Vector3(1, 0, 0),
})

export function BladeViewer({
  url,
  onError,
  guides = [],
  guidesEnabled = false,
  guideStatus,
}: {
  url?: string
  onError?: (message: string) => void
  guides?: StationGuide[]
  guidesEnabled?: boolean
  guideStatus?: string
}) {
  const host = useRef<HTMLDivElement>(null)
  const actions = useRef<ViewActions>(emptyActions())
  const errorCallback = useRef(onError)
  const sceneRef = useRef<THREE.Scene | undefined>(undefined)
  const modelBoxRef = useRef<THREE.Box3 | undefined>(undefined)
  const guideLayerRef = useRef<THREE.Group | undefined>(undefined)
  const guidesRef = useRef(guides)
  const guidesEnabledRef = useRef(guidesEnabled)
  const showGuidesRef = useRef(true)
  const [state, setState] = useState<'empty' | 'loading' | 'ready' | 'error'>(url ? 'loading' : 'empty')
  const [expanded, setExpanded] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('face')
  const [showGuides, setShowGuides] = useState(true)

  const syncGuides = () => {
    disposeStationGuideGroup(guideLayerRef.current)
    guideLayerRef.current = undefined
    if (!sceneRef.current || !modelBoxRef.current || !guidesEnabledRef.current || !showGuidesRef.current) return
    const layer = createStationGuideGroup(guidesRef.current, modelBoxRef.current)
    sceneRef.current.add(layer)
    guideLayerRef.current = layer
  }

  useEffect(() => { errorCallback.current = onError }, [onError])
  useEffect(() => {
    guidesRef.current = guides
    guidesEnabledRef.current = guidesEnabled
    showGuidesRef.current = showGuides
    syncGuides()
  }, [guides, guidesEnabled, showGuides])
  useEffect(() => {
    if (!expanded) return
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setExpanded(false)
    }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [expanded])

  useEffect(() => {
    const element = host.current
    if (!element || !url) {
      setState('empty')
      return
    }

    let disposed = false
    let frame = 0
    let mesh: THREE.Mesh | undefined
    let directions = defaultDirections()
    setState('loading')
    setViewMode('face')
    errorCallback.current?.('')

    const scene = new THREE.Scene()
    sceneRef.current = scene
    scene.background = new THREE.Color(0x101820)
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000)
    scene.add(camera)
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    element.replaceChildren(renderer.domElement)

    scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 2.2))
    const cameraLight = new THREE.DirectionalLight(0xffffff, 1.5)
    cameraLight.position.set(0, 0, 1)
    camera.add(cameraLight)
    scene.add(new THREE.AxesHelper(35))
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true

    const frameModel = (requestedDirection: THREE.Vector3, requestedUp: THREE.Vector3) => {
      if (!mesh || disposed) return
      const box = new THREE.Box3().setFromObject(mesh)
      const fitted = calculateCameraFrame(box, requestedDirection, requestedUp, camera.aspect, camera.fov)
      controls.target.copy(fitted.center)
      camera.position.copy(fitted.center).addScaledVector(fitted.direction, fitted.distance)
      camera.up.copy(fitted.up)
      camera.near = fitted.near
      camera.far = fitted.far
      camera.updateProjectionMatrix()
      controls.update()
    }

    const currentDirection = () => {
      const direction = camera.position.clone().sub(controls.target)
      return direction.lengthSq() > 1e-10 ? direction.normalize() : directions.face.clone()
    }

    actions.current = {
      fit: () => frameModel(currentDirection(), camera.up),
      face: () => {
        setViewMode('face')
        frameModel(directions.face, new THREE.Vector3(0, 1, 0))
      },
      edge: () => {
        setViewMode('edge')
        frameModel(directions.edge, new THREE.Vector3(0, 1, 0))
      },
      isometric: () => {
        setViewMode('isometric')
        const direction = directions.face.clone().addScaledVector(directions.edge, .55).add(new THREE.Vector3(0, .25, 0)).normalize()
        frameModel(direction, radialUp(direction))
      },
    }

    const resize = () => {
      if (disposed) return
      const width = Math.max(element.clientWidth, 1)
      const height = Math.max(element.clientHeight, 1)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height, false)
    }
    const observer = new ResizeObserver(resize)
    observer.observe(element)
    resize()

    new STLLoader().load(
      url,
      geometry => {
        if (disposed) {
          geometry.dispose()
          return
        }
        geometry.computeVertexNormals()
        directions = deriveBladeViewDirections(geometry)
        mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: 0xd8dde3, metalness: .12, roughness: .5 }))
        scene.add(mesh)
        modelBoxRef.current = new THREE.Box3().setFromObject(mesh)
        syncGuides()
        actions.current.face()
        setState('ready')
      },
      undefined,
      error => {
        if (disposed) return
        const message = error instanceof Error ? error.message : 'The STL preview could not be loaded'
        setState('error')
        errorCallback.current?.(message)
      },
    )

    const draw = () => {
      if (disposed) return
      frame = requestAnimationFrame(draw)
      controls.update()
      renderer.render(scene, camera)
    }
    draw()

    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      observer.disconnect()
      controls.dispose()
      disposeStationGuideGroup(guideLayerRef.current)
      guideLayerRef.current = undefined
      modelBoxRef.current = undefined
      sceneRef.current = undefined
      scene.traverse(object => {
        if ('geometry' in object && object.geometry instanceof THREE.BufferGeometry) object.geometry.dispose()
        if ('material' in object) {
          const material = object.material as THREE.Material | THREE.Material[]
          if (Array.isArray(material)) material.forEach(value => value.dispose())
          else material?.dispose()
        }
      })
      renderer.dispose()
      renderer.forceContextLoss()
      element.replaceChildren()
      actions.current = emptyActions()
    }
  }, [url])

  const visibleGuides = guidesEnabled && showGuides ? guides : []
  return (
    <div className={`viewer-shell ${expanded ? 'expanded' : ''}`} role={expanded ? 'dialog' : undefined} aria-modal={expanded || undefined} aria-label={expanded ? 'Expanded blade viewer' : undefined} data-view={viewMode} data-guide-count={visibleGuides.length}>
      <div className="viewer-host" ref={host}>
        {!url && <p>Generate a blade to load its OCP-derived STL preview.</p>}
        {state === 'loading' && <p className="viewer-overlay">Loading preview…</p>}
        {state === 'error' && <p className="viewer-overlay error">Preview failed to load</p>}
      </div>
      <div className="station-guide-controls">
        <label className="inline"><input type="checkbox" checked={showGuides} onChange={event => setShowGuides(event.target.checked)} /> Show Station Guides</label>
        {guideStatus && <p className={!guidesEnabled ? 'station-guide-stale' : 'hint'}>{guideStatus}</p>}
        {visibleGuides.length > 0 && <ul className="station-guide-legend" aria-label="Station guide legend">{visibleGuides.map(guide => <li key={guide.id} style={{ '--guide-color': `#${guide.color.toString(16).padStart(6, '0')}` } as React.CSSProperties} data-world-y-mm={guide.yMm.toFixed(6)}><strong>{guide.label}</strong>: r/R {guide.rOverR.toFixed(4)} · Y {guide.yMm.toFixed(3)} mm</li>)}</ul>}
      </div>
      <div className="viewer-tools">
        <span>{state === 'ready' ? 'OCP solid preview' : state === 'loading' ? 'Loading preview…' : ''}</span>
        <div>
          <button disabled={state !== 'ready'} aria-pressed={viewMode === 'face'} onClick={() => actions.current.face()}>Blade Face View</button>
          <button disabled={state !== 'ready'} aria-pressed={viewMode === 'edge'} onClick={() => actions.current.edge()}>Blade Edge View</button>
          <button disabled={state !== 'ready'} aria-pressed={viewMode === 'isometric'} onClick={() => actions.current.isometric()}>Isometric View</button>
          <button disabled={state !== 'ready'} onClick={() => actions.current.fit()}>Fit to Model</button>
          <button onClick={() => setExpanded(value => !value)}>{expanded ? 'Restore Viewer' : 'Expand Viewer'}</button>
        </div>
      </div>
    </div>
  )
}
