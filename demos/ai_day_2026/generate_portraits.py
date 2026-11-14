"""Pre-render actual pinned G1 portraits and selection animations, offline."""
import sys, base64, math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco as mj
from showcase_render import png

ROOT=Path(__file__).resolve().parents[2]
WIDTH,HEIGHT,COLS,FRAMES=360,480,6,60
TINTS={'periodic':[.58,.81,1], 'age':[1,.76,.34], 'uncertainty':[.76,.55,1]}

# Authored pose keyframes: time, root height, yaw, pitch, backward/forward
# translation, joint offsets. Angles are radians. No dynamics are simulated.
def arms(l,r,le,re,lp=0,rp=0):
    return {'left_shoulder_roll_joint':l,'right_shoulder_roll_joint':r,
            'left_elbow_joint':le,'right_elbow_joint':re,
            'left_shoulder_pitch_joint':lp,'right_shoulder_pitch_joint':rp}
def legs(lh,rh,lk,rk,la,ra,lr=0,rr=0):
    return {'left_hip_pitch_joint':lh,'right_hip_pitch_joint':rh,
            'left_knee_joint':lk,'right_knee_joint':rk,
            'left_ankle_pitch_joint':la,'right_ankle_pitch_joint':ra,
            'left_hip_roll_joint':lr,'right_hip_roll_joint':rr}
def crouch(k=1):
    return legs(-.82*k,-.82*k,1.55*k,1.55*k,-.70*k,-.70*k)
def K(t,z=0,yaw=0,pitch=0,x=0,j=None):
    return (t,z,yaw,pitch,x,j or {})
TUCK={**legs(-1.15,-1.15,1.85,1.85,-.45,-.45),**arms(.15,-.15,.35,.35,-.65,-.65)}
VICTORY={**legs(-.15,.37,.25,.48,-.11,-.35,.05,-.09),
         **arms(-.13,-.12,-1.50,.10,-.78,.15),'left_shoulder_yaw_joint':-.18,'waist_roll_joint':-.10}
BALLET={**legs(0,-.95,.07,2.10,-.12,.12,0,-.64),
        **arms(.10,-.10,-.66,-.66,-2.75,-2.75),
        'right_hip_yaw_joint':-.95,'left_shoulder_yaw_joint':-.16,'right_shoulder_yaw_joint':.16}
BOW={**legs(-.72,-.79,1.30,1.55,-.46,-.52,.12,-.46),
     **arms(1.05,-1.05,-.28,-.28,-.18,-.18),'right_hip_yaw_joint':-.68,'waist_pitch_joint':.52}
STANCE={**legs(-.28,.28,.35,.45,-.14,-.22,.13,-.10),
        **arms(-.10,.10,-1.75,-1.75,-.68,-.70),
        'left_shoulder_yaw_joint':-.10,'right_shoulder_yaw_joint':.10,'waist_yaw_joint':.12,'waist_pitch_joint':.28}
def punch(left):
    p=STANCE.copy()
    if left:
        p.update(arms(-.08,.10,.22,-1.75,-1.65,-.70))
        p.update(waist_yaw_joint=.28,waist_pitch_joint=.32)
    else:
        p.update(arms(-.10,.08,-1.75,.22,-.68,-1.72))
        p.update(waist_yaw_joint=-.40,waist_pitch_joint=.36,
                 right_hip_yaw_joint=-.22,right_ankle_pitch_joint=-.38)
    return p
WINDUP={**STANCE,**arms(-.10,.18,-1.75,-1.36,-.68,.83),
        'waist_yaw_joint':.65,'right_shoulder_yaw_joint':.28}
MOTIONS={
 'periodic':[
    K(0),K(.10,-.13,0,.14,0,{**crouch(.6),**arms(.1,-.1,-.45,-.45,.65,.65)}),
    K(.20,-.28,0,.23,0,{**crouch(),**arms(.08,-.08,-.70,-.70,.95,.95)}),
    K(.29,.04,0,-.18,-.02,arms(.16,-.16,-.35,-.35,-2.0,-2.0)),
    K(.37,.42,0,-1.22,-.06,TUCK),K(.44,.62,0,-math.pi,-.11,TUCK),
    K(.52,.38,0,-5.0,-.17,TUCK),
    K(.59,.04,0,-math.tau,-.21,{**crouch(.50),**arms(.35,-.35,-.3,-.3,-.55,-.55)}),
    K(.65,-.25,0,-math.tau,-.21,{**crouch(.90),**arms(.40,-.40,-.20,-.20,-.6,-.6)}),
    K(.74,-.04,0,-math.tau,-.16,{**VICTORY, **arms(.18,-.12,-.35,.10,-2.55,.15)}),
    K(.84,-.04,0,-math.tau,-.16,VICTORY),K(.93,-.04,0,-math.tau,-.16,VICTORY),
    K(1,0,0,-math.tau,0,{})],
 'age':[
    K(0),K(.13,-.08,-.27,0,0,{**crouch(.36),**arms(.85,-.85,-.60,-.60,-.5,-.5)}),
    K(.23,.02,0,0,0,BALLET),K(.37,.02,math.tau,0,0,BALLET),
    K(.53,.02,2*math.tau,0,0,BALLET),
    K(.65,-.10,2*math.tau,0,0,{**crouch(.40),**arms(1.0,-1.0,-.75,-.75,-.18,-.18)}),
    K(.77,-.26,2*math.tau,.23,0,BOW),K(.89,-.26,2*math.tau,.23,0,BOW),
    K(1,0,2*math.tau,0,0,{})],
 'uncertainty':[
    K(0),K(.15,-.045,.20,0,.02,STANCE),
    K(.23,-.04,.30,0,.065,punch(True)),K(.30,-.045,.20,0,.02,STANCE),
    K(.38,-.04,.30,0,.065,punch(True)),K(.44,-.045,.20,0,.02,STANCE),
    K(.50,-.055,.45,0,-.015,WINDUP),K(.60,-.04,-.36,0,.10,punch(False)),K(.70,-.045,.20,0,.02,STANCE),
    K(.86,-.045,.20,0,.02,STANCE),K(1)]
}
def sample(name,t):
    frames=MOTIONS[name]
    for (t0,z0,y0,p0,x0,a),(t1,z1,y1,p1,x1,b) in zip(frames,frames[1:]):
        if t<=t1:
            u=max(0,min(1,(t-t0)/(t1-t0)))
            smooth=u*u*(3-2*u)
            # Do not stop and restart at the middle of a continuous rotation.
            turn=u if (name=='age' and .23<=t0<.53) or (name=='periodic' and .29<=t0<.59) else smooth
            return (z0+(z1-z0)*smooth,y0+(y1-y0)*turn,
                    p0+(p1-p0)*turn,x0+(x1-x0)*smooth,
                    {k:a.get(k,0)+(b.get(k,0)-a.get(k,0))*smooth for k in a.keys()|b.keys()})
    return frames[-1][1:]

def generate(out, motion=None, reaction=None):
    src=ROOT/'third_party/unitree_g1/g1.xml'
    root=ET.parse(src).getroot()
    root.find('compiler').set('meshdir',str(src.parent/'assets'))
    visual=root.find('visual')
    if visual is None: visual=ET.SubElement(root,'visual')
    glob=visual.find('global')
    if glob is None: glob=ET.SubElement(visual,'global')
    glob.set('offwidth',str(WIDTH));glob.set('offheight',str(HEIGHT))
    head=visual.find('headlight')
    if head is None: head=ET.SubElement(visual,'headlight')
    head.attrib.update(ambient='.26 .26 .26',diffuse='.45 .45 .45',specular='.18 .18 .18')
    wb=root.find('worldbody')
    # Fixed rubber-hand meshes cannot articulate. Provide a presentation-only
    # glove alternative; toggle opacity per strategy below.
    for body in wb.iter('body'):
        for geom in list(body.findall('geom')):
            mesh=geom.get('mesh')
            if mesh in ('left_rubber_hand','right_rubber_hand'):
                side=mesh.split('_')[0]
                geom.set('name',side+'_open_showcase')
                ET.SubElement(body,'geom',name=side+'_fist_showcase',type='ellipsoid',
                    size='.052 .040 .043',pos='.073 0 0',rgba='.20 .21 .24 0',
                    group='2',contype='0',conaffinity='0',mass='0')
    for node in list(wb):
        if node.tag in ('light','camera'): wb.remove(node)
    for pos,direction,power in [('3 -4 5','-3 4 -4','.48 .48 .48'),('3 4 3','-3 -4 -2','.26 .26 .26'),('-3 0 4','3 0 -3','.32 .32 .32')]:
        ET.SubElement(wb,'light',pos=pos,dir=direction,diffuse=power,ambient='.035 .035 .035',castshadow='false')
    model=mj.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
    data=mj.MjData(model)
    key=mj.mj_name2id(model,mj.mjtObj.mjOBJ_KEY,'stand')
    root_joint=mj.mj_name2id(model,mj.mjtObj.mjOBJ_JOINT,'floating_base_joint')
    adr=int(model.jnt_qposadr[root_joint])
    original=model.geom_rgba.copy();materials=model.geom_matid.copy()
    camera=mj.MjvCamera();mj.mjv_defaultCamera(camera)
    camera.type=mj.mjtCamera.mjCAMERA_FREE
    camera.lookat[:]=(-.04,0,.83);camera.distance=2.65;camera.azimuth=150;camera.elevation=-8
    opt=mj.MjvOption();mj.mjv_defaultOption(opt);opt.sitegroup[:]=0
    opt.geomgroup[2]=1;opt.geomgroup[3]=0
    out.mkdir(parents=True,exist_ok=True)
    def save(name,rgb):
        path=out/name;tmp=out/(name+'.tmp')
        tmp.write_bytes(base64.b64decode(png(rgb)));tmp.replace(path)
    left_foot=mj.mj_name2id(model,mj.mjtObj.mjOBJ_SITE,'left_foot')
    mj.mj_resetDataKeyframe(model,data,key);mj.mj_forward(model,data)
    anchor=data.site_xpos[left_foot,:2].copy() if left_foot>=0 else None
    def pose(name,t=None):
        mj.mj_resetDataKeyframe(model,data,key)
        if reaction=='defeat' or t is not None:
            if reaction=='defeat':
                z,yaw,pitch,x,joints=(-.15,0,.37,0,{**legs(-.40,-.40,.76,.76,-.30,-.30),
                    **arms(.10,-.10,-.22,-.22,.32,.32), 'waist_pitch_joint':.48})
            else:
                z,yaw,pitch,x,joints=sample(name,t)
            data.qpos[adr]+=x;data.qpos[adr+2]+=z
            cy,sy,cp,sp=math.cos(yaw/2),math.sin(yaw/2),math.cos(pitch/2),math.sin(pitch/2)
            data.qpos[adr+3:adr+7]=(cy*cp,-sy*sp,cy*sp,sy*cp)
            for joint,delta in joints.items():
                i=mj.mj_name2id(model,mj.mjtObj.mjOBJ_JOINT,joint)
                if i<0: continue
                q=int(model.jnt_qposadr[i]);v=data.qpos[q]+delta
                data.qpos[q]=np.clip(v,*model.jnt_range[i]) if model.jnt_limited[i] else v
        mj.mj_forward(model,data)
        if name=='age' and t is not None and anchor is not None and .13<t<.65:
            weight=min(1,(t-.13)/.10,(.65-t)/.12)
            data.qpos[adr:adr+2]+=(anchor-data.site_xpos[left_foot,:2])*weight
            mj.mj_forward(model,data)
    with mj.Renderer(model,height=HEIGHT,width=WIDTH) as renderer:
        for name in ([motion] if motion else TINTS):
            tint=np.array(TINTS[name])
            model.geom_rgba[:]=original;model.geom_matid[:]=materials
            for idx in range(model.ngeom):
                if model.geom_group[idx]!=2 or model.geom_type[idx]!=mj.mjtGeom.mjGEOM_MESH: continue
                mat=int(materials[idx]);base=model.mat_rgba[mat,:3] if mat>=0 else original[idx,:3]
                model.geom_rgba[idx,:3]=np.maximum(base,.20) if np.mean(base)<.35 else np.clip(base*.30+tint*.70,0,1)
                model.geom_rgba[idx,3]=1;model.geom_matid[idx]=-1
            for side in ('left','right'):
                opened=mj.mj_name2id(model,mj.mjtObj.mjOBJ_GEOM,side+'_open_showcase')
                fist=mj.mj_name2id(model,mj.mjtObj.mjOBJ_GEOM,side+'_fist_showcase')
                if opened>=0 and fist>=0:
                    model.geom_rgba[opened,3]=0 if name=='uncertainty' and motion and not reaction else 1
                    model.geom_rgba[fist,3]=1 if name=='uncertainty' and motion and not reaction else 0
            def render(t=None):
                pose(name,t)
                renderer.update_scene(data,camera=camera,scene_option=opt)
                rgb=renderer.render().copy()
                renderer.enable_segmentation_rendering()
                try:
                    renderer.update_scene(data,camera=camera,scene_option=opt)
                    segmentation=renderer.render()
                    alpha=np.where(segmentation[:,:,1]==int(mj.mjtObj.mjOBJ_GEOM),255,0).astype(np.uint8)
                finally:
                    renderer.disable_segmentation_rendering()
                return np.dstack((rgb,alpha))
            if reaction=='defeat':
                save(name+'-defeat.png',render())
            elif not motion:
                save(name+'.png',render())
            else:
                sheet=np.zeros((HEIGHT*((FRAMES+COLS-1)//COLS),WIDTH*COLS,4),dtype=np.uint8)
                for i in range(FRAMES):
                    y,x=divmod(i,COLS)
                    sheet[y*HEIGHT:(y+1)*HEIGHT,x*WIDTH:(x+1)*WIDTH]=render(i/(FRAMES-1))
                save(name+'-motion.png',sheet)
if __name__=='__main__':
    generate(Path(sys.argv[1]),sys.argv[2] if len(sys.argv)>2 else None,
             sys.argv[3] if len(sys.argv)>3 else None)
