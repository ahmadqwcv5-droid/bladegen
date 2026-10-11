import * as THREE from 'three'

export type BladeViewDirections = {
  face: THREE.Vector3
  edge: THREE.Vector3
}

export type CameraFrame = {
  center: THREE.Vector3
  direction: THREE.Vector3
  up: THREE.Vector3
  distance: number
  near: number
  far: number
}

const RADIAL_AXIS = new THREE.Vector3(0, 1, 0)

function canonicalDirection(direction: THREE.Vector3): THREE.Vector3 {
  const normalized = direction.clone().normalize()
  if (normalized.z < -1e-9 || (Math.abs(normalized.z) <= 1e-9 && normalized.x < 0)) {
    normalized.negate()
  }
  return normalized
}

/**
 * Find the dominant pressure/suction-surface normal in the transverse XZ plane.
 * Opposing face normals contribute identically through their outer products,
 * while the much smaller edge and cap faces have proportionally less area.
 */
export function deriveBladeViewDirections(geometry: THREE.BufferGeometry): BladeViewDirections {
  const positions = geometry.getAttribute('position')
  if (!positions || positions.count < 3) {
    return { face: new THREE.Vector3(0, 0, 1), edge: new THREE.Vector3(1, 0, 0) }
  }

  const index = geometry.getIndex()
  const triangleCount = Math.floor((index?.count ?? positions.count) / 3)
  const a = new THREE.Vector3()
  const b = new THREE.Vector3()
  const c = new THREE.Vector3()
  const ab = new THREE.Vector3()
  const ac = new THREE.Vector3()
  const normal = new THREE.Vector3()
  let xx = 0
  let xz = 0
  let zz = 0

  const vertex = (triangleVertex: number, target: THREE.Vector3) => {
    const positionIndex = index ? index.getX(triangleVertex) : triangleVertex
    target.fromBufferAttribute(positions, positionIndex)
  }

  for (let triangle = 0; triangle < triangleCount; triangle += 1) {
    const start = triangle * 3
    vertex(start, a)
    vertex(start + 1, b)
    vertex(start + 2, c)
    ab.subVectors(b, a)
    ac.subVectors(c, a)
    normal.crossVectors(ab, ac)
    const doubleArea = normal.length()
    if (doubleArea <= 1e-12) continue
    normal.multiplyScalar(1 / doubleArea)
    xx += doubleArea * normal.x * normal.x
    xz += doubleArea * normal.x * normal.z
    zz += doubleArea * normal.z * normal.z
  }

  if (xx + zz <= 1e-12) {
    return { face: new THREE.Vector3(0, 0, 1), edge: new THREE.Vector3(1, 0, 0) }
  }

  const angle = 0.5 * Math.atan2(2 * xz, xx - zz)
  const face = canonicalDirection(new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle)))
  const edge = canonicalDirection(new THREE.Vector3(-face.z, 0, face.x))
  return { face, edge }
}

export function radialUp(direction: THREE.Vector3): THREE.Vector3 {
  const unitDirection = direction.clone().normalize()
  const projected = RADIAL_AXIS.clone().addScaledVector(
    unitDirection,
    -RADIAL_AXIS.dot(unitDirection),
  )
  if (projected.lengthSq() > 1e-10) return projected.normalize()
  return new THREE.Vector3(0, 0, 1)
}

function boxCorners(box: THREE.Box3): THREE.Vector3[] {
  const { min, max } = box
  return [
    new THREE.Vector3(min.x, min.y, min.z),
    new THREE.Vector3(min.x, min.y, max.z),
    new THREE.Vector3(min.x, max.y, min.z),
    new THREE.Vector3(min.x, max.y, max.z),
    new THREE.Vector3(max.x, min.y, min.z),
    new THREE.Vector3(max.x, min.y, max.z),
    new THREE.Vector3(max.x, max.y, min.z),
    new THREE.Vector3(max.x, max.y, max.z),
  ]
}

/** Calculate a perspective-camera distance that fits every bounding-box corner. */
export function calculateCameraFrame(
  box: THREE.Box3,
  requestedDirection: THREE.Vector3,
  requestedUp: THREE.Vector3,
  aspect: number,
  verticalFovDegrees: number,
  padding = 1.12,
): CameraFrame {
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  const radius = Math.max(size.length() / 2, 0.001)
  const direction = requestedDirection.clone().normalize()
  let up = requestedUp.clone().addScaledVector(
    direction,
    -requestedUp.dot(direction),
  )
  if (up.lengthSq() <= 1e-10) up = radialUp(direction)
  up.normalize()
  const right = new THREE.Vector3().crossVectors(up, direction).normalize()
  up = new THREE.Vector3().crossVectors(direction, right).normalize()

  const tanVertical = Math.tan(THREE.MathUtils.degToRad(verticalFovDegrees / 2))
  const tanHorizontal = tanVertical * Math.max(aspect, 1e-6)
  let distance = radius

  for (const corner of boxCorners(box)) {
    const offset = corner.sub(center)
    const along = offset.dot(direction)
    const horizontal = Math.abs(offset.dot(right)) / tanHorizontal
    const vertical = Math.abs(offset.dot(up)) / tanVertical
    distance = Math.max(distance, along + Math.max(horizontal, vertical) * padding)
  }

  return {
    center,
    direction,
    up,
    distance,
    near: Math.max(radius / 1000, 0.001),
    far: Math.max(distance + radius * 4, 100),
  }
}
