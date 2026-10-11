import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import {
  calculateCameraFrame,
  deriveBladeViewDirections,
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

  it('fits every box corner in both wide and narrow perspective viewports', () => {
    const box = new THREE.Box3(
      new THREE.Vector3(-30, 40, -12),
      new THREE.Vector3(35, 200, 16),
    )
    const direction = new THREE.Vector3(0, 0, 1)
    const distances: number[] = []

    for (const aspect of [1.8, 0.2]) {
      const frame = calculateCameraFrame(box, direction, new THREE.Vector3(0, 1, 0), aspect, 40)
      distances.push(frame.distance)
      const camera = new THREE.PerspectiveCamera(40, aspect, frame.near, frame.far)
      camera.position.copy(frame.center).addScaledVector(frame.direction, frame.distance)
      camera.up.copy(frame.up)
      camera.lookAt(frame.center)
      camera.updateMatrixWorld(true)
      for (const x of [box.min.x, box.max.x]) {
        for (const y of [box.min.y, box.max.y]) {
          for (const z of [box.min.z, box.max.z]) {
            const projected = new THREE.Vector3(x, y, z).project(camera)
            expect(Math.abs(projected.x)).toBeLessThanOrEqual(1)
            expect(Math.abs(projected.y)).toBeLessThanOrEqual(1)
            expect(projected.z).toBeGreaterThanOrEqual(-1)
            expect(projected.z).toBeLessThanOrEqual(1)
          }
        }
      }
    }
    expect(distances[1]).toBeGreaterThan(distances[0])
  })
})
