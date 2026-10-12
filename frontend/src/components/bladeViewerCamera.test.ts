import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import {
  boxCorners,
  calculateCameraFrame,
  deriveBladeViewDirections,
  measureBoxProjection,
  radialUp,
} from './bladeViewerCamera'

function broadBladeGeometry(angleDegrees = 0): THREE.BufferGeometry {
  const angle = THREE.MathUtils.degToRad(angleDegrees)
  const chord = new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle))
  const normal = new THREE.Vector3(-chord.z, 0, chord.x)
  const vertices: number[] = []
  for (const side of [-1, 1]) {
    const offset = normal.clone().multiplyScalar(side)
    const points = [
      chord.clone().multiplyScalar(-25).add(new THREE.Vector3(0, 0, 0)).add(offset),
      chord.clone().multiplyScalar(25).add(new THREE.Vector3(0, 0, 0)).add(offset),
      chord.clone().multiplyScalar(18).add(new THREE.Vector3(0, 180, 0)).add(offset),
      chord.clone().multiplyScalar(-18).add(new THREE.Vector3(0, 180, 0)).add(offset),
    ]
    for (const index of [0, 1, 2, 0, 2, 3]) vertices.push(...points[index].toArray())
  }
  return new THREE.BufferGeometry().setAttribute(
    'position',
    new THREE.Float32BufferAttribute(vertices, 3),
  )
}

describe('blade viewer camera', () => {
  it('derives orthogonal broad-face and edge directions from blade surfaces', () => {
    const geometry = broadBladeGeometry(32)
    const { face, edge } = deriveBladeViewDirections(geometry)
    const expectedFace = new THREE.Vector3(-Math.sin(THREE.MathUtils.degToRad(32)), 0, Math.cos(THREE.MathUtils.degToRad(32)))
    expect(Math.abs(face.dot(expectedFace))).toBeGreaterThan(0.999)
    expect(Math.abs(face.dot(edge))).toBeLessThan(1e-9)
    geometry.dispose()
  })

  it('keeps the radial axis visually upright for face, edge, and isometric views', () => {
    for (const direction of [
      new THREE.Vector3(0, 0, 1),
      new THREE.Vector3(1, 0, 0),
      new THREE.Vector3(1, 0.35, 1),
    ]) {
      const up = radialUp(direction)
      expect(Math.abs(up.dot(direction.clone().normalize()))).toBeLessThan(1e-9)
      expect(up.y).toBeGreaterThan(0)
    }
  })

  const fixtures = {
    longNarrow: new THREE.Box3(new THREE.Vector3(-30, 40, -12), new THREE.Vector3(35, 200, 16)),
    shortWide: new THREE.Box3(new THREE.Vector3(-130, -16, -9), new THREE.Vector3(145, 28, 13)),
    asymmetricOffset: new THREE.Box3(new THREE.Vector3(72, -35, -91), new THREE.Vector3(249, 19, 38)),
  }

  function fittedCamera(box: THREE.Box3, aspect: number, direction = new THREE.Vector3(.31, .18, 1)) {
    const frame = calculateCameraFrame(box, direction, radialUp(direction), aspect, 40)
    const camera = new THREE.PerspectiveCamera(40, aspect, frame.near, frame.far)
    camera.position.copy(frame.center).addScaledVector(frame.direction, frame.distance)
    camera.up.copy(frame.up)
    camera.lookAt(frame.center)
    camera.updateProjectionMatrix()
    camera.updateMatrixWorld(true)
    return { camera, frame, projection: measureBoxProjection(box, camera) }
  }

  it.each(Object.entries(fixtures))('fits every %s box corner across required viewport transitions', (_, box) => {
    const direction = new THREE.Vector3(.31, .18, 1).normalize()
    for (const aspect of [1.8, 1.2, .75, .5]) {
      const { camera, frame, projection } = fittedCamera(box, aspect, direction)
      expect(camera.aspect).toBe(aspect)
      expect(projection.contained).toBe(true)
      expect(frame.near).toBeGreaterThan(0)
      expect(frame.far).toBeGreaterThan(frame.near)
      expect(Math.max(projection.maxAbsX, projection.maxAbsY)).toBeGreaterThan(.7)
      expect(frame.direction.angleTo(direction)).toBeLessThan(1e-10)
      for (const corner of boxCorners(box)) {
        const projected = corner.project(camera)
        expect(projected.x).toBeGreaterThanOrEqual(-1.000001)
        expect(projected.x).toBeLessThanOrEqual(1.000001)
        expect(projected.y).toBeGreaterThanOrEqual(-1.000001)
        expect(projected.y).toBeLessThanOrEqual(1.000001)
        expect(projected.z).toBeGreaterThanOrEqual(-1.000001)
        expect(projected.z).toBeLessThanOrEqual(1.000001)
      }
    }
  })

  it('refits wide-to-narrow and narrow-to-wide without changing orientation', () => {
    const box = fixtures.shortWide
    const direction = new THREE.Vector3(.7, .2, 1).normalize()
    const wide = fittedCamera(box, 1.8, direction)
    const narrow = fittedCamera(box, .5, direction)
    const restored = fittedCamera(box, 1.8, direction)

    expect(narrow.frame.distance).toBeGreaterThan(wide.frame.distance)
    expect(restored.frame.distance).toBeCloseTo(wide.frame.distance, 10)
    expect(narrow.frame.direction.angleTo(wide.frame.direction)).toBeLessThan(1e-10)
    expect(restored.frame.direction.angleTo(wide.frame.direction)).toBeLessThan(1e-10)
    expect(wide.projection.contained).toBe(true)
    expect(narrow.projection.contained).toBe(true)
    expect(restored.projection.contained).toBe(true)
  })
})
