import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import example from '../../examples/custom_multi_airfoil_finite_te.json'
import App from './App'

const api=vi.hoisted(()=>({getExample:vi.fn(),validate:vi.fn(),build:vi.fn(),getJob:vi.fn(),getArtifacts:vi.fn()}))
vi.mock('./api/client',()=>api)
vi.mock('./components/BladeViewer',()=>({BladeViewer:({url}:{url?:string})=><div data-testid="viewer">{url??'empty'}</div>}))

afterEach(() => cleanup())

const validation={solidification:{solid_after_reimport:{solids:1,closed_shell:true,brepcheck_valid:true,free_edges:0,volume_mm3:12,volume_method:'adaptive'},roundtrip:{one_solid:true,volume_delta_mm3:0}},geometry_validation:{passed:true,max_chord_error_mm:.001,max_twist_error_deg:.001,max_reference_axis_error_mm:.001,max_te_error_mm:.001,control_contour_rms_max_mm:.001,control_contour_p95_max_mm:.001,control_contour_max_mm:.001,root_measurement:{requested_r_over_R:.2,measured_r_over_R:.203},tip_measurement:{requested_r_over_R:1,measured_r_over_R:.9995},stations:[]}}

beforeEach(()=>{api.getExample.mockResolvedValue(structuredClone(example));api.validate.mockResolvedValue({valid:true});api.build.mockResolvedValue({job_id:'a'.repeat(32),status:'queued'});api.getJob.mockResolvedValue({job_id:'a'.repeat(32),status:'succeeded'});api.getArtifacts.mockResolvedValue([{name:'blade_preview.stl',size_bytes:1,download_url:'/preview'},{name:'validation.json',size_bytes:1,download_url:'/validation'}]);vi.stubGlobal('fetch',vi.fn().mockResolvedValue({json:async()=>validation}));vi.stubGlobal('confirm',vi.fn(()=>true));vi.stubGlobal('crypto',{randomUUID:vi.fn(()=>Math.random().toString(36))})})

async function loaded(){render(<App/>);await screen.findByText('Airfoil Stations (5)')}

describe('Sprint 02 editor',()=>{
  it('adds and removes stable airfoil rows',async()=>{const user=userEvent.setup();await loaded();await user.click(screen.getByRole('button',{name:'Add Airfoil Station'}));expect(screen.getByText('Airfoil Stations (6)')).toBeInTheDocument();const table=screen.getByText('Airfoil Stations (6)').closest('section')!;const enabled=within(table).getAllByRole('button',{name:'Remove'}).filter(button=>!button.hasAttribute('disabled'));await user.click(enabled[0]);expect(screen.getByText('Airfoil Stations (5)')).toBeInTheDocument()})
  it('synchronizes a root edit across stations and independent curves',async()=>{await loaded();const root=screen.getByLabelText('Root radius');fireEvent.change(root,{target:{value:'0.18'}});fireEvent.blur(root);await waitFor(()=>expect(screen.getByLabelText('Airfoil radius 1')).toHaveValue(0.18));expect(screen.getByLabelText('Chord radius 1')).toHaveValue(0.18);expect(screen.getByLabelText('Twist radius 1')).toHaveValue(0.18)})
  it('preserves NACA leading zeroes and coordinates effective thickness',async()=>{const user=userEvent.setup();await loaded();const code=screen.getByLabelText('NACA code 5');await user.clear(code);await user.type(code,'0008');expect(code).toHaveValue('0008');expect(screen.queryByText(/does not match NACA 0008/)).not.toBeInTheDocument()})
  it('edits curve counts and interpolation independently',async()=>{const user=userEvent.setup();await loaded();const chord=screen.getByText('Chord (6)').closest('section')!;await user.click(within(chord).getByRole('button',{name:'Add Control Point'}));expect(screen.getByText('Chord (7)')).toBeInTheDocument();expect(screen.getByText('Twist (6)')).toBeInTheDocument();await user.selectOptions(screen.getByLabelText('Twist interpolation'),'linear');expect(screen.getByLabelText('Twist interpolation')).toHaveValue('linear')})
  it('imports BladeSpec JSON without losing station counts',async()=>{const user=userEvent.setup();await loaded();const imported=structuredClone(example);imported.airfoil_sections=imported.airfoil_sections.slice(0,3);imported.airfoil_sections[2]=structuredClone(example.airfoil_sections.at(-1)!);const file=new File([JSON.stringify(imported)],'three.json',{type:'application/json'});await user.upload(document.querySelector('input[type=file]') as HTMLInputElement,file);expect(await screen.findByText('Airfoil Stations (3)')).toBeInTheDocument()})
  it('binds results to a job snapshot and marks later edits stale',async()=>{const user=userEvent.setup();await loaded();await user.click(screen.getByRole('button',{name:'Generate Blade'}));expect(await screen.findByText('STEP topology')).toBeInTheDocument();const name=screen.getByLabelText('Name');await user.clear(name);await user.type(name,'changed');expect(screen.getByText(/Inputs changed — regenerate/)).toBeInTheDocument();expect(screen.getByText(/Preview from job aaaaaaaa/)).toBeInTheDocument()})
})
