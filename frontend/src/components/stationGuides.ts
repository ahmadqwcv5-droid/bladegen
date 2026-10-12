import * as THREE from 'three'

export type StationGuide = {
  id: string
  label: string
  rOverR: number
  yMm: number
  color: number
  role: 'selected' | 'A' | 'B'
}

export const STATION_A_COLOR = 0xf08a3c
export const STATION_B_COLOR = 0x29a3a3
export const STATION_GUIDE_PLANE_NORMAL = Object.freeze({ x: 0, y: 1, z: 0 })

export function stationYmm(diameterMm: number, rOverR: number): number {
  if (!Number.isFinite(diameterMm) || diameterMm <= 0) throw new Error('Diameter must be positive')
  if (!Number.isFinite(rOverR) || rOverR < 0 || rOverR > 1) throw new Error('Station r/R must be within [0, 1]')
  return diameterMm * .5 * rOverR
}

export function makeStationGuide(
  id: string,
  index: number,
  diameterMm: number,
  rOverR: number,
  role: StationGuide['role'],
): StationGuide {
  return {
    id,
    label: role === 'selected' ? `Station ${index + 1}` : `Station ${role} · ${index + 1}`,
    rOverR,
    yMm: stationYmm(diameterMm, rOverR),
    color: role === 'B' ? STATION_B_COLOR : STATION_A_COLOR,
    role,
  }
}

export function createStationGuideGroup(guides: StationGuide[], modelBox: THREE.Box3): THREE.Group {
  const layer = new THREE.Group()
  layer.name = 'station-guides'
  const size = modelBox.getSize(new THREE.Vector3())
  const center = modelBox.getCenter(new THREE.Vector3())
  const width = Math.max(size.x * 1.18, 20)
  const depth = Math.max(size.z * 1.18, 20)
  const markerX = center.x + width * .55

  for (const guide of guides) {
    const group = new THREE.Group()
    group.name = `station-guide-${guide.id}`
    group.userData = { ...guide, planeNormal: STATION_GUIDE_PLANE_NORMAL }

    const planeGeometry = new THREE.PlaneGeometry(width, depth)
    planeGeometry.rotateX(Math.PI / 2)
    const planeMaterial = new THREE.MeshBasicMaterial({
      color: guide.color,
      transparent: true,
      opacity: .12,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
    const plane = new THREE.Mesh(planeGeometry, planeMaterial)
    plane.position.set(center.x, guide.yMm, center.z)
    plane.renderOrder = 2
    group.add(plane)

    const rectangle = [
      new THREE.Vector3(center.x - width / 2, guide.yMm, center.z - depth / 2),
      new THREE.Vector3(center.x + width / 2, guide.yMm, center.z - depth / 2),
      new THREE.Vector3(center.x + width / 2, guide.yMm, center.z + depth / 2),
      new THREE.Vector3(center.x - width / 2, guide.yMm, center.z + depth / 2),
    ]
    const outline = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(rectangle),
      new THREE.LineBasicMaterial({ color: guide.color, transparent: true, opacity: .95 }),
    )
    outline.renderOrder = 3
    group.add(outline)

    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(Math.max(Math.min(width, depth) * .025, 1.5), 16, 12),
      new THREE.MeshBasicMaterial({ color: guide.color }),
    )
    marker.position.set(markerX, guide.yMm, center.z)
    marker.renderOrder = 4
    group.add(marker)
    layer.add(group)
  }
  return layer
}

export function disposeStationGuideGroup(group?: THREE.Group): void {
  if (!group) return
  group.traverse(object => {
    if ('geometry' in object && object.geometry instanceof THREE.BufferGeometry) object.geometry.dispose()
    if ('material' in object) {
      const material = object.material as THREE.Material | THREE.Material[]
      if (Array.isArray(material)) material.forEach(value => value.dispose())
      else material?.dispose()
    }
  })
  group.removeFromParent()
}
