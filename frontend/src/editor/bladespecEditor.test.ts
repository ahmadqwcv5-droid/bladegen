import { describe,expect,it } from 'vitest'
import example from '../../../examples/custom_multi_airfoil_finite_te.json'
import { addAirfoilStation,addControlPoint,canonicalJson,changeRootRadius,coordinateNacaThickness,parseBladeSpec,removeAirfoilStation,removeControlPoint,setThicknessOverride,validateEditorSpec } from './bladespecEditor'
import type { BladeSpec } from '../types/bladespec'

const source=()=>structuredClone(example) as BladeSpec

describe('BladeSpec engineering editor',()=>{
  it('adds and removes an airfoil station without leaking row metadata',()=>{ const added=addAirfoilStation(source(),.7,'0012'); expect(added.airfoil_sections).toHaveLength(6); expect(added.airfoil_sections[3].r_over_R).toBe(.7); expect(removeAirfoilStation(added,3).airfoil_sections).toHaveLength(5); expect(canonicalJson(added)).not.toContain('rowId') })
  it('rejects a duplicate airfoil radius',()=>expect(()=>addAirfoilStation(source(),.6)).toThrow(/already exists/))
  it('synchronizes root and all independent distribution roots',()=>{ const next=changeRootRadius(source(),.18); expect(next.airfoil_sections[0].r_over_R).toBe(.18); for(const key of ['chord_distribution','twist_distribution','rake_distribution','skew_distribution','thickness_distribution'] as const) expect(next[key].points[0].r_over_R).toBe(.18) })
  it('edits independent curve point counts and preserves interpolation',()=>{ const spec=source(); const chord=addControlPoint(spec.chord_distribution,'chord_over_R',.425); expect(chord.points).toHaveLength(7); expect(chord.interpolation).toBe('pchip'); expect(removeControlPoint(chord,2).points).toHaveLength(6); expect(spec.twist_distribution.points).toHaveLength(6) })
  it('preserves leading zeroes and coordinates non-coincident thickness',()=>{ const spec=source(); const added=addAirfoilStation(spec,.7,'0008'); const index=added.airfoil_sections.findIndex(s=>s.r_over_R===.7); expect(added.airfoil_sections[index].airfoil).toEqual({type:'naca4',code:'0008'}); const coordinated=coordinateNacaThickness(added,index,'0010'); expect(validateEditorSpec(coordinated)).toEqual([]) })
  it('coordinates an explicit thickness override with its radial curve value',()=>{ const spec=source(); const index=1, radius=spec.airfoil_sections[index].r_over_R; spec.thickness_distribution.points=spec.thickness_distribution.points.filter(p=>p.r_over_R!==radius); const next=setThicknessOverride(spec,index,.105); expect(next.airfoil_sections[index].thickness_override_ratio).toBe(.105); expect(next.thickness_distribution.points.find(p=>p.r_over_R===radius)?.thickness_ratio).toBe(.105); expect(validateEditorSpec(next)).toEqual([]) })
  it('round-trips all neutral JSON inputs',()=>{ const spec=source(); expect(parseBladeSpec(canonicalJson(spec))).toEqual(spec) })
  it('detects changed input snapshots',()=>{ const before=source(), snapshot=canonicalJson(before); const after={...before,name:'changed'}; expect(canonicalJson(after)).not.toBe(snapshot) })
})
