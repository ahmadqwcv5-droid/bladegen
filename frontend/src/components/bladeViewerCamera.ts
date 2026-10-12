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

export type CameraProjection = {
  contained: boolean
  maxAbsX: number
  maxAbsY: number
  minZ: number
  maxZ: number
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

export function boxCorners(box: THREE.Box3): THREE.Vector3[] {
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
    distance = Math.max(distance, along + radius * .05)
  }

  let nearestDepth = Number.POSITIVE_INFINITY
  let farthestDepth = 0
  for (const corner of boxCorners(box)) {
    const depth = distance - corner.sub(center).dot(direction)
    nearestDepth = Math.min(nearestDepth, depth)
    farthestDepth = Math.max(farthestDepth, depth)
  }
  const near = Math.max(nearestDepth * .5, 0.001)
  const far = Math.max(farthestDepth * 1.5, near + 1)

  return {
    center,
    direction,
    up,
    distance,
    near,
    far,
  }
}

/** Measure authoritative model-box containment using the camera's real projection. */
export function measureBoxProjection(
  box: THREE.Box3,
  camera: THREE.PerspectiveCamera,
  tolerance = 1e-6,
): CameraProjection {
  camera.updateMatrixWorld(true)
  const projected = boxCorners(box).map(corner => corner.project(camera))
  const maxAbsX = Math.max(...projected.map(point => Math.abs(point.x)))
  const maxAbsY = Math.max(...projected.map(point => Math.abs(point.y)))
  const minZ = Math.min(...projected.map(point => point.z))
  const maxZ = Math.max(...projected.map(point => point.z))
  return {
    contained: maxAbsX <= 1 + tolerance
      && maxAbsY <= 1 + tolerance
      && minZ >= -1 - tolerance
      && maxZ <= 1 + tolerance,
    maxAbsX,
    maxAbsY,
    minZ,
    maxZ,
  }
}
