import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import {
  createStationGuideGroup,
  disposeStationGuideGroup,
  makeStationGuide,
  STATION_GUIDE_PLANE_NORMAL,
  stationYmm,
} from './stationGuides'

describe('station guide coordinates', () => {
  it.each([
    [400, .2, 40],
    [400, .6, 120],
    [400, 1, 200],
    [400, .18, 36],
    [720, .4, 144],
  ])('places D=%s r/R=%s at Y=%s mm', (diameter, radius, expected) => {
    expect(stationYmm(diameter, radius)).toBe(expected)
  })

  it('rejects invalid engineering coordinates', () => {
    expect(() => stationYmm(0, .2)).toThrow(/Diameter/)
    expect(() => stationYmm(400, 1.01)).toThrow(/r\/R/)
  })

  it('uses the BladeSpec position independently of visual bounds and creates an XZ plane', () => {
    const guide = makeStationGuide('station-3', 2, 400, .6, 'selected')
    const compact = createStationGuideGroup(
      [guide],
      new THREE.Box3(new THREE.Vector3(-2, 37, -1), new THREE.Vector3(8, 179, 3)),
    )
    const huge = createStationGuideGroup(
      [guide],
      new THREE.Box3(new THREE.Vector3(-900, -800, -700), new THREE.Vector3(900, 800, 700)),
    )
    const compactPlane = compact.getObjectByProperty('type', 'Mesh') as THREE.Mesh<THREE.PlaneGeometry>
    const hugePlane = huge.getObjectByProperty('type', 'Mesh') as THREE.Mesh<THREE.PlaneGeometry>

    expect(compactPlane.position.y).toBe(120)
    expect(hugePlane.position.y).toBe(120)
    expect(STATION_GUIDE_PLANE_NORMAL).toEqual({ x: 0, y: 1, z: 0 })
    const normals = compactPlane.geometry.attributes.normal
    for (let index = 0; index < normals.count; index += 1) {
      expect(Math.abs(normals.getY(index))).toBeCloseTo(1, 6)
      expect(normals.getX(index)).toBeCloseTo(0, 6)
      expect(normals.getZ(index)).toBeCloseTo(0, 6)
    }
    disposeStationGuideGroup(compact)
    disposeStationGuideGroup(huge)
  })

  it('disposes every replaced guide geometry and material', () => {
    const group = createStationGuideGroup(
      [makeStationGuide('a', 0, 400, .2, 'A'), makeStationGuide('b', 3, 400, .8, 'B')],
      new THREE.Box3(new THREE.Vector3(-10, 40, -5), new THREE.Vector3(10, 200, 5)),
    )
    const geometrySpies: ReturnType<typeof vi.spyOn>[] = []
    const materialSpies: ReturnType<typeof vi.spyOn>[] = []
    group.traverse(object => {
      if ('geometry' in object && object.geometry instanceof THREE.BufferGeometry) geometrySpies.push(vi.spyOn(object.geometry, 'dispose'))
      if ('material' in object && object.material instanceof THREE.Material) materialSpies.push(vi.spyOn(object.material, 'dispose'))
    })

    disposeStationGuideGroup(group)

    expect(geometrySpies).toHaveLength(6)
    expect(materialSpies).toHaveLength(6)
    geometrySpies.forEach(spy => expect(spy).toHaveBeenCalledOnce())
    materialSpies.forEach(spy => expect(spy).toHaveBeenCalledOnce())
  })
})
