import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'

export function BladeViewer({url}: {url?: string}) {
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!host.current || !url) return
    const element = host.current
    const scene = new THREE.Scene(); scene.background = new THREE.Color(0x101820)
    const camera = new THREE.PerspectiveCamera(40, element.clientWidth / 420, .1, 5000)
    const renderer = new THREE.WebGLRenderer({antialias: true}); renderer.setSize(element.clientWidth, 420)
    element.replaceChildren(renderer.domElement)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 2.4))
    const controls = new OrbitControls(camera, renderer.domElement)
    let frame = 0
    new STLLoader().load(url, geometry => {
      geometry.computeVertexNormals(); geometry.center()
      const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color: 0xd8dde3, metalness: .15, roughness: .52}))
      scene.add(mesh)
      const size = new THREE.Box3().setFromObject(mesh).getSize(new THREE.Vector3()).length()
      camera.position.set(size * .8, size * .6, size * .8); camera.near = size / 1000; camera.far = size * 20; camera.updateProjectionMatrix()
      controls.target.set(0,0,0); controls.update()
    })
    const draw = () => { frame = requestAnimationFrame(draw); controls.update(); renderer.render(scene, camera) }; draw()
    return () => { cancelAnimationFrame(frame); controls.dispose(); renderer.dispose(); element.replaceChildren() }
  }, [url])
  return <div className="viewer">{url ? <div ref={host}/> : <p>Generate a blade to load its OCP-derived STL preview.</p>}</div>
}
