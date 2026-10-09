import type { AirfoilSection, BladeSpec, Distribution, Point } from '../types/bladespec'

const EPS = 1e-10

export function canonicalJson(spec: BladeSpec): string {
  return JSON.stringify(spec)
}

function slopes(x: number[], y: number[]): number[] {
  const n = x.length
  if (n === 2) return [(y[1]-y[0])/(x[1]-x[0]), (y[1]-y[0])/(x[1]-x[0])]
  const h = x.slice(0,-1).map((v,i)=>x[i+1]-v)
  const d = h.map((v,i)=>(y[i+1]-y[i])/v)
  const m = Array(n).fill(0)
  for (let k=1;k<n-1;k++) {
    if (d[k-1]===0 || d[k]===0 || Math.sign(d[k-1])!==Math.sign(d[k])) m[k]=0
    else { const w1=2*h[k]+h[k-1], w2=h[k]+2*h[k-1]; m[k]=(w1+w2)/(w1/d[k-1]+w2/d[k]) }
  }
  const endpoint=(h0:number,h1:number,d0:number,d1:number)=>{
    let value=((2*h0+h1)*d0-h0*d1)/(h0+h1)
    if (Math.sign(value)!==Math.sign(d0)) value=0
    else if (Math.sign(d0)!==Math.sign(d1) && Math.abs(value)>3*Math.abs(d0)) value=3*d0
    return value
  }
  m[0]=endpoint(h[0],h[1],d[0],d[1]); m[n-1]=endpoint(h[n-2],h[n-3],d[n-2],d[n-3])
  return m
}

export function evaluateDistribution(distribution: Distribution, valueKey: string, radius: number): number {
  const points=distribution.points
  if (radius < points[0].r_over_R-EPS || radius > points.at(-1)!.r_over_R+EPS) throw new Error('Radius is outside the distribution domain')
  const exact=points.find(point=>Math.abs(point.r_over_R-radius)<=EPS)
  if (exact) return exact[valueKey]
  const right=points.findIndex(point=>point.r_over_R>radius), left=right-1
  const x=points.map(p=>p.r_over_R), y=points.map(p=>p[valueKey])
  if (distribution.interpolation==='linear') return y[left]+(radius-x[left])*(y[right]-y[left])/(x[right]-x[left])
  const m=slopes(x,y), h=x[right]-x[left], t=(radius-x[left])/h
  return (2*t**3-3*t**2+1)*y[left]+(t**3-2*t**2+t)*h*m[left]+(-2*t**3+3*t**2)*y[right]+(t**3-t**2)*h*m[right]
}

export function addControlPoint(distribution: Distribution, valueKey: string, radius: number): Distribution {
  if (!Number.isFinite(radius)) throw new Error('Control radius must be finite')
  if (distribution.points.some(p=>Math.abs(p.r_over_R-radius)<=EPS)) throw new Error(`A control point already exists at r/R=${radius}`)
  const value=evaluateDistribution(distribution,valueKey,radius)
  return {...distribution,points:[...distribution.points,{r_over_R:radius,[valueKey]:value}].sort((a,b)=>a.r_over_R-b.r_over_R)}
}

export function removeControlPoint(distribution: Distribution, index: number): Distribution {
  if (distribution.points.length<=2) throw new Error('A distribution requires at least two control points')
  if (index===0 || index===distribution.points.length-1) throw new Error('Root and tip control points are required')
  return {...distribution,points:distribution.points.filter((_,i)=>i!==index)}
}

export function updateControlPoint(distribution: Distribution, index: number, update: Record<string, number>): Distribution {
  const points=distribution.points.map((point,i)=>i===index?{...point,...update}:point)
  if (points.some((point,i)=>i>0 && point.r_over_R<=points[i-1].r_over_R)) throw new Error('Control radii must be strictly increasing with no duplicates')
  return {...distribution,points}
}

export function changeRootRadius(spec: BladeSpec, radius: number): BladeSpec {
  if (!Number.isFinite(radius) || radius<=0 || radius>=1) throw new Error('Root radius must be between 0 and 1')
  const nextRadii=[spec.airfoil_sections[1].r_over_R, spec.chord_distribution.points[1].r_over_R, spec.twist_distribution.points[1].r_over_R, spec.rake_distribution.points[1].r_over_R, spec.skew_distribution.points[1].r_over_R, spec.thickness_distribution.points[1].r_over_R]
  if (nextRadii.some(next=>radius>=next)) throw new Error(`Root radius must be below every next station (${Math.min(...nextRadii)})`)
  const first=(distribution:Distribution):Distribution=>({...distribution,points:distribution.points.map((p,i)=>i===0?{...p,r_over_R:radius}:p)})
  return {...spec,root_radius_ratio:radius,airfoil_sections:spec.airfoil_sections.map((s,i)=>i===0?{...s,r_over_R:radius}:s),chord_distribution:first(spec.chord_distribution),twist_distribution:first(spec.twist_distribution),rake_distribution:first(spec.rake_distribution),skew_distribution:first(spec.skew_distribution),thickness_distribution:first(spec.thickness_distribution)}
}

function nominal(code:string):number { return Number(code.slice(2))/100 }

export function effectiveThickness(spec:BladeSpec, section:AirfoilSection):number {
  return section.thickness_override_ratio ?? evaluateDistribution(spec.thickness_distribution,'thickness_ratio',section.r_over_R)
}

export function setThicknessOverride(spec:BladeSpec,index:number,ratio:number):BladeSpec {
  if (!Number.isFinite(ratio) || ratio<=0) throw new Error("Thickness override must be positive and finite")
  const radius=spec.airfoil_sections[index].r_over_R
  let thickness=spec.thickness_distribution
  let exact=thickness.points.findIndex(p=>Math.abs(p.r_over_R-radius)<=EPS)
  if (exact<0) { thickness=addControlPoint(thickness,"thickness_ratio",radius); exact=thickness.points.findIndex(p=>Math.abs(p.r_over_R-radius)<=EPS) }
  thickness=updateControlPoint(thickness,exact,{thickness_ratio:ratio})
  return {...spec,thickness_distribution:thickness,airfoil_sections:spec.airfoil_sections.map((section,i)=>i===index?{...section,thickness_override_ratio:ratio}:section)}
}

export function coordinateNacaThickness(spec:BladeSpec,index:number,code:string):BladeSpec {
  if (!/^\d{4}$/.test(code)) return {...spec,airfoil_sections:spec.airfoil_sections.map((s,i)=>i===index?{...s,airfoil:{type:'naca4',code}}:s)}
  const section=spec.airfoil_sections[index], ratio=nominal(code)
  let thickness=spec.thickness_distribution
  if (section.thickness_override_ratio===undefined) {
    const exact=thickness.points.findIndex(p=>Math.abs(p.r_over_R-section.r_over_R)<=EPS)
    thickness=exact>=0?updateControlPoint(thickness,exact,{thickness_ratio:ratio}):addControlPoint(thickness,'thickness_ratio',section.r_over_R)
    if (exact<0) { const inserted=thickness.points.findIndex(p=>Math.abs(p.r_over_R-section.r_over_R)<=EPS); thickness=updateControlPoint(thickness,inserted,{thickness_ratio:ratio}) }
  }
  return {...spec,thickness_distribution:thickness,airfoil_sections:spec.airfoil_sections.map((s,i)=>i===index?{...s,airfoil:{type:'naca4',code}}:s)}
}

export function addAirfoilStation(spec:BladeSpec,radius:number,code='0012'):BladeSpec {
  if (radius<=spec.root_radius_ratio || radius>=1) throw new Error('New airfoil station must be inside the root-to-tip domain')
  if (spec.airfoil_sections.some(s=>Math.abs(s.r_over_R-radius)<=EPS)) throw new Error(`An airfoil station already exists at r/R=${radius}`)
  const left=[...spec.airfoil_sections].reverse().find(s=>s.r_over_R<radius)!, right=spec.airfoil_sections.find(s=>s.r_over_R>radius)!
  const f=(radius-left.r_over_R)/(right.r_over_R-left.r_over_R)
  const te=left.trailing_edge_thickness_mm+(right.trailing_edge_thickness_mm-left.trailing_edge_thickness_mm)*f
  const section:AirfoilSection={r_over_R:radius,airfoil:{type:'naca4',code},trailing_edge_thickness_mm:te}
  let next={...spec,airfoil_sections:[...spec.airfoil_sections,section].sort((a,b)=>a.r_over_R-b.r_over_R)}
  const index=next.airfoil_sections.findIndex(s=>s===section)
  next=coordinateNacaThickness(next,index,code)
  return next
}

export function removeAirfoilStation(spec:BladeSpec,index:number):BladeSpec {
  if (spec.airfoil_sections.length<=2) throw new Error('At least two airfoil stations are required')
  if (index===0 || index===spec.airfoil_sections.length-1) throw new Error('Root and tip airfoil stations are required')
  return {...spec,airfoil_sections:spec.airfoil_sections.filter((_,i)=>i!==index)}
}

export function validateEditorSpec(spec:BladeSpec):string[] {
  const errors:string[]=[]
  if (spec.airfoil_sections.length<2) errors.push('At least two airfoil stations are required')
  if (spec.airfoil_sections.some((s,i)=>i>0&&s.r_over_R<=spec.airfoil_sections[i-1].r_over_R)) errors.push('Airfoil radii must be strictly increasing with no duplicates')
  if (spec.airfoil_sections[0]?.r_over_R!==spec.root_radius_ratio) errors.push('Root radius and first airfoil station disagree')
  if (spec.airfoil_sections.at(-1)?.r_over_R!==1) errors.push('The tip airfoil station must remain at r/R=1.0')
  for (const section of spec.airfoil_sections) if (section.airfoil.type==='naca4') {
    if (!/^\d{4}$/.test(section.airfoil.code)) errors.push(`Invalid NACA code at r/R=${section.r_over_R}`)
    else if (section.thickness_override_ratio===undefined && Math.abs(effectiveThickness(spec,section)-nominal(section.airfoil.code))>1e-6) errors.push(`Thickness at r/R=${section.r_over_R} does not match NACA ${section.airfoil.code}; coordinate the curve or enable an override`)
  }
  return errors
}

export function parseBladeSpec(text:string):BladeSpec {
  const value=JSON.parse(text) as BladeSpec
  if (!value || !Array.isArray(value.airfoil_sections)) throw new Error('File is not a BladeSpec JSON document')
  return value
}
