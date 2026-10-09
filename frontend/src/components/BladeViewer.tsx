import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'

type ViewActions = {
  fit: () => void
  isometric: () => void
  front: () => void
  side: () => void
}

const emptyActions = (): ViewActions => ({
  fit: () => undefined,
  isometric: () => undefined,
  front: () => undefined,
  side: () => undefined,
})

export function BladeViewer({ url, onError }: { url?: string; onError?: (message: string) => void }) {
  const host = useRef<HTMLDivElement>(null)
  const actions = useRef<ViewActions>(emptyActions())
  const errorCallback = useRef(onError)
  const [state, setState] = useState<'empty' | 'loading' | 'ready' | 'error'>(url ? 'loading' : 'empty')
  const [expanded, setExpanded] = useState(false)

  useEffect(() => { errorCallback.current = onError }, [onError])
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
    setState('loading')
    errorCallback.current?.('')

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x101820)
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000)
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    element.replaceChildren(renderer.domElement)

    scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 2.4))
    scene.add(new THREE.DirectionalLight(0xffffff, 1.3))
    scene.add(new THREE.AxesHelper(35))
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    let mesh: THREE.Mesh | undefined

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

    const frameModel = (direction: THREE.Vector3) => {
      if (!mesh) return
      const box = new THREE.Box3().setFromObject(mesh)
      const size = box.getSize(new THREE.Vector3())
      const center = box.getCenter(new THREE.Vector3())
      const radius = Math.max(size.length() / 2, 0.001)
      const distance = radius / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.25
      controls.target.copy(center)
      camera.position.copy(center).add(direction.clone().normalize().multiplyScalar(distance))
      camera.near = Math.max(radius / 1000, 0.001)
      camera.far = Math.max(radius * 30, 100)
      camera.up.set(0, 1, 0)
      camera.updateProjectionMatrix()
      controls.update()
    }
    actions.current = {
      fit: () => frameModel(new THREE.Vector3(1, 0.7, 1)),
      isometric: () => frameModel(new THREE.Vector3(1, 1, 1)),
      front: () => frameModel(new THREE.Vector3(0, 0, 1)),
      side: () => frameModel(new THREE.Vector3(1, 0, 0)),
    }

    new STLLoader().load(
      url,
      geometry => {
        if (disposed) {
          geometry.dispose()
          return
        }
        geometry.computeVertexNormals()
        mesh = new THREE.Mesh(
          geometry,
          new THREE.MeshStandardMaterial({ color: 0xd8dde3, metalness: 0.15, roughness: 0.52 }),
        )
        scene.add(mesh)
        actions.current.fit()
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
      scene.traverse(object => {
        if ('geometry' in object && object.geometry instanceof THREE.BufferGeometry) {
          object.geometry.dispose()
        }
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

  return (
    <div
      className={`viewer-shell ${expanded ? 'expanded' : ''}`}
      role={expanded ? 'dialog' : undefined}
      aria-modal={expanded || undefined}
      aria-label={expanded ? 'Expanded blade viewer' : undefined}
    >
      <div className="viewer-host" ref={host}>
        {!url && <p>Generate a blade to load its OCP-derived STL preview.</p>}
        {state === 'loading' && <p className="viewer-overlay">Loading preview…</p>}
        {state === 'error' && <p className="viewer-overlay error">Preview failed to load</p>}
      </div>
      <div className="viewer-tools">
        <span>{state === 'ready' ? 'OCP solid preview' : state === 'loading' ? 'Loading preview…' : ''}</span>
        <div>
          <button disabled={state !== 'ready'} onClick={() => actions.current.fit()}>Fit to Model</button>
          <button disabled={state !== 'ready'} onClick={() => actions.current.isometric()}>Isometric</button>
          <button disabled={state !== 'ready'} onClick={() => actions.current.front()}>Front</button>
          <button disabled={state !== 'ready'} onClick={() => actions.current.side()}>Side</button>
          <button onClick={() => setExpanded(value => !value)}>{expanded ? 'Restore Viewer' : 'Expand Viewer'}</button>
        </div>
      </div>
    </div>
  )
}
