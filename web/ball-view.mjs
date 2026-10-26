import * as T from "./vendor/three/three.module.js";

export const BALL_RADIUS = .16; // Existing display radius; source centre/height stay exact.

export function ballDrawScale(depth, fov, cssHeight) {
  if(![depth,fov,cssHeight].every(Number.isFinite) || depth<=0 || cssHeight<=0 || fov<=0 || fov>=180) return 1;
  const pixels=BALL_RADIUS*cssHeight/(depth*Math.tan(fov*Math.PI/360));
  // A restrained presentation adjustment for wide/reduced-motion views only.
  // Never a trajectory adjustment, glow or through-player rendering.
  return Math.max(1,Math.min(1.5,5/pixels));
}

export function createBall() {
  const ball=new T.Mesh(new T.SphereGeometry(BALL_RADIUS,20,14),
    new T.MeshStandardMaterial({color:0xfffdf2,roughness:.38}));
  ball.castShadow=true;ball.visible=false;
  // Twelve solid dark pentagons give stable contrast at small projected sizes;
  // a wireframe alone disappears along bright pitch markings.
  const source=new T.IcosahedronGeometry(1,0),positions=source.getAttribute("position"),directions=new Map();
  for(let i=0;i<positions.count;i++){
    const normal=new T.Vector3().fromBufferAttribute(positions,i).normalize();
    directions.set(normal.toArray().map(v=>v.toFixed(4)).join(),normal);
  }
  const triangles=[];
  for(const normal of directions.values()){
    const centre=normal.clone().multiplyScalar(BALL_RADIUS+.001);
    const tangent=new T.Vector3(0,1,0).cross(normal);
    if(tangent.lengthSq()<.001)tangent.set(1,0,0);tangent.normalize();
    const up=normal.clone().cross(tangent),ring=[];
    for(let i=0;i<5;i++)ring.push(centre.clone().addScaledVector(tangent,.046*Math.cos(i*Math.PI*2/5))
      .addScaledVector(up,.046*Math.sin(i*Math.PI*2/5)).normalize().multiplyScalar(BALL_RADIUS+.001));
    for(let i=0;i<5;i++)triangles.push(...centre.toArray(),...ring[i].toArray(),...ring[(i+1)%5].toArray());
  }
  source.dispose();
  const patches=new T.BufferGeometry();patches.setAttribute("position",new T.Float32BufferAttribute(triangles,3));patches.computeVertexNormals();
  ball.add(new T.Mesh(patches,new T.MeshStandardMaterial({color:0x15212c,roughness:.6,side:T.DoubleSide})));
  ball.add(new T.Mesh(new T.SphereGeometry(BALL_RADIUS*1.045,16,10),
    new T.MeshBasicMaterial({color:0x22302e,side:T.BackSide})));
  return ball;
}
