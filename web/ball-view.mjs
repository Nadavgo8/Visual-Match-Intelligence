import * as T from "./vendor/three/three.module.js";

export const BALL_RADIUS = .16; // Existing display radius; source centre/height stay exact.

export function ballDrawScale(depth, fov, cssHeight) {
  if(![depth,fov,cssHeight].every(Number.isFinite) || depth<=0 || cssHeight<=0 || fov<=0 || fov>=180) return 1;
  const pixels=BALL_RADIUS*cssHeight/(depth*Math.tan(fov*Math.PI/360));
  // The ball must survive ordinary CSS-resolution viewing, not just a zoomed
  // framebuffer. This is bounded display scaling at the exact source centre;
  // depth testing still lets an actually occluding body cover it.
  const minimum = cssHeight >= 600 ? 9.5 : 7.5;
  return Math.max(1,Math.min(1.6,minimum/pixels));
}

export function createBall() {
  const ball=new T.Mesh(new T.SphereGeometry(BALL_RADIUS,20,14),
    new T.MeshStandardMaterial({color:0xffffff,roughness:.46,
      emissive:0xffffff,emissiveIntensity:.12}));
  ball.castShadow=true;ball.visible=false;
  // Twelve solid dark pentagons give stable contrast at small projected sizes;
  // a wireframe alone disappears along bright pitch markings.
  const source=new T.IcosahedronGeometry(1,0),positions=source.getAttribute("position"),directions=new Map();
  for(let i=0;i<positions.count;i++){
    const normal=new T.Vector3().fromBufferAttribute(positions,i).normalize();
    directions.set(normal.toArray().map(v=>v.toFixed(4)).join(),normal);
  }
  const triangles=[];
  // Flat pentagon fans cut through a sphere: their interior used to disappear
  // under the white shell. Project subdivided triangles onto the same curved
  // surface so every panel remains solid at ordinary viewing distance.
  const panelRadius=BALL_RADIUS+.0015;
  const addTriangle=(a,b,c,level=2)=>{
    if(level===0){triangles.push(...a.toArray(),...b.toArray(),...c.toArray());return;}
    const ab=a.clone().add(b).normalize().multiplyScalar(panelRadius);
    const bc=b.clone().add(c).normalize().multiplyScalar(panelRadius);
    const ca=c.clone().add(a).normalize().multiplyScalar(panelRadius);
    addTriangle(a,ab,ca,level-1);addTriangle(ab,b,bc,level-1);
    addTriangle(ca,bc,c,level-1);addTriangle(ab,bc,ca,level-1);
  };
  for(const normal of directions.values()){
    const centre=normal.clone().multiplyScalar(panelRadius);
    const tangent=new T.Vector3(0,1,0).cross(normal);
    if(tangent.lengthSq()<.001)tangent.set(1,0,0);tangent.normalize();
    const up=normal.clone().cross(tangent),ring=[];
    for(let i=0;i<5;i++)ring.push(centre.clone().addScaledVector(tangent,.046*Math.cos(i*Math.PI*2/5))
      .addScaledVector(up,.046*Math.sin(i*Math.PI*2/5)).normalize().multiplyScalar(panelRadius));
    for(let i=0;i<5;i++)addTriangle(centre,ring[i],ring[(i+1)%5]);
  }
  source.dispose();
  const patches=new T.BufferGeometry();patches.setAttribute("position",new T.Float32BufferAttribute(triangles,3));patches.computeVertexNormals();
  ball.add(new T.Mesh(patches,new T.MeshStandardMaterial({color:0x15212c,roughness:.6,side:T.DoubleSide})));
  ball.add(new T.Mesh(new T.SphereGeometry(BALL_RADIUS*1.12,20,14),
    new T.MeshBasicMaterial({color:0x22302e,side:T.BackSide})));
  return ball;
}
