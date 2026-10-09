import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'

export function BladeViewer({url}:{url?:string}) {
  const host=useRef<HTMLDivElement>(null); const fit=useRef<()=>void>(()=>{}); const [state,setState]=useState<'empty'|'loading'|'ready'|'error'>(url?'loading':'empty')
  useEffect(()=>{
    if(!host.current||!url){setState('empty');return}
    setState('loading');const element=host.current;const scene=new THREE.Scene();scene.background=new THREE.Color(0x101820)
    const camera=new THREE.PerspectiveCamera(40,Math.max(element.clientWidth,1)/420,.1,5000);const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));renderer.setSize(element.clientWidth,420);element.replaceChildren(renderer.domElement)
    scene.add(new THREE.HemisphereLight(0xffffff,0x334455,2.4));scene.add(new THREE.AxesHelper(35));const controls=new OrbitControls(camera,renderer.domElement);let mesh:THREE.Mesh|undefined;let frame=0
    fit.current=()=>{if(!mesh)return;const box=new THREE.Box3().setFromObject(mesh),size=box.getSize(new THREE.Vector3()).length(),center=box.getCenter(new THREE.Vector3());controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(size*.8,size*.6,size*.8));camera.near=Math.max(size/1000,.001);camera.far=size*20;camera.updateProjectionMatrix();controls.update()}
    new STLLoader().load(url,geometry=>{geometry.computeVertexNormals();mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0xd8dde3,metalness:.15,roughness:.52}));scene.add(mesh);fit.current();setState('ready')},undefined,()=>setState('error'))
    const resize=()=>{const width=Math.max(element.clientWidth,1);camera.aspect=width/420;camera.updateProjectionMatrix();renderer.setSize(width,420)};window.addEventListener('resize',resize)
    const draw=()=>{frame=requestAnimationFrame(draw);controls.update();renderer.render(scene,camera)};draw()
    return()=>{cancelAnimationFrame(frame);window.removeEventListener('resize',resize);controls.dispose();if(mesh){mesh.geometry.dispose();(mesh.material as THREE.Material).dispose()}renderer.dispose();element.replaceChildren();fit.current=()=>{}}
  },[url])
  return <div className="viewer-shell"><div className="viewer">{url?<div ref={host}/>:<p>Generate a blade to load its OCP-derived STL preview.</p>}</div><div className="viewer-tools"><span>{state==='loading'?'Loading preview…':state==='error'?'Preview failed to load':state==='ready'?'OCP solid preview':''}</span><button disabled={state!=='ready'} onClick={()=>fit.current()}>Fit to model</button></div></div>
}
