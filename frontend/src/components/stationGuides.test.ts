import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import {
  createStationGuideGroup,
  disposeStationGuideGroup,
  makeStationGuide,
  StationGuideLayerController,
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

  it('does not reconstruct semantically unchanged guides from a new array', () => {
    const scene = new THREE.Scene()
    const box = new THREE.Box3(new THREE.Vector3(-10, 40, -5), new THREE.Vector3(10, 200, 5))
    const create = vi.fn(createStationGuideGroup)
    const dispose = vi.fn(disposeStationGuideGroup)
    const controller = new StationGuideLayerController(create, dispose)
    const first = [makeStationGuide('station-3', 2, 400, .6, 'selected')]
    const equivalent = [makeStationGuide('station-3', 2, 400, .6, 'selected')]

    expect(controller.sync(scene, box, first, true)).toBe(true)
    const originalLayer = controller.currentLayer()
    expect(controller.sync(scene, box.clone(), equivalent, true)).toBe(false)
    expect(controller.currentLayer()).toBe(originalLayer)
    expect(create).toHaveBeenCalledOnce()
    expect(dispose).not.toHaveBeenCalled()
    controller.dispose()
  })

  it('replaces changed selections, comparison pairs, and model bounds', () => {
    const scene = new THREE.Scene()
    const box = new THREE.Box3(new THREE.Vector3(-10, 40, -5), new THREE.Vector3(10, 200, 5))
    const create = vi.fn(createStationGuideGroup)
    const dispose = vi.fn(disposeStationGuideGroup)
    const controller = new StationGuideLayerController(create, dispose)
    const station3 = [makeStationGuide('station-3', 2, 400, .6, 'selected')]
    const station4 = [makeStationGuide('station-4', 3, 400, .8, 'selected')]
    const comparison = [
      makeStationGuide('station-1', 0, 400, .2, 'A'),
      makeStationGuide('station-4', 3, 400, .8, 'B'),
    ]

    controller.sync(scene, box, station3, true)
    expect(controller.sync(scene, box, station4, true)).toBe(true)
    expect(controller.sync(scene, box, comparison, true)).toBe(true)
    expect(controller.sync(scene, box.clone().expandByScalar(5), comparison, true)).toBe(true)
    expect(create).toHaveBeenCalledTimes(4)
    expect(dispose).toHaveBeenCalledTimes(3)
    controller.dispose()
    expect(dispose).toHaveBeenCalledTimes(4)
  })

  it('removes and restores guides without touching primary STL resources', () => {
    const scene = new THREE.Scene()
    const primaryGeometry = new THREE.BoxGeometry(20, 160, 10)
    const primaryMaterial = new THREE.MeshBasicMaterial()
    const geometryDispose = vi.spyOn(primaryGeometry, 'dispose')
    const materialDispose = vi.spyOn(primaryMaterial, 'dispose')
    const primary = new THREE.Mesh(primaryGeometry, primaryMaterial)
    scene.add(primary)
    const box = new THREE.Box3().setFromObject(primary)
    const controller = new StationGuideLayerController()
    const guides = [makeStationGuide('station-3', 2, 400, .6, 'selected')]

    expect(controller.sync(scene, box, guides, true)).toBe(true)
    expect(controller.sync(scene, box, guides, false)).toBe(true)
    expect(controller.currentLayer()).toBeUndefined()
    expect(controller.sync(scene, box, guides, false)).toBe(false)
    expect(controller.sync(scene, box, guides, true)).toBe(true)
    expect(scene.children).toContain(primary)
    expect(geometryDispose).not.toHaveBeenCalled()
    expect(materialDispose).not.toHaveBeenCalled()

    controller.dispose()
    primaryGeometry.dispose()
    primaryMaterial.dispose()
  })
})
