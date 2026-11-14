"""Pre-render actual pinned G1 portraits and selection animations, offline."""
import sys, base64, math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco as mj
from showcase_render import png

ROOT=Path(__file__).resolve().parents[2]
WIDTH,HEIGHT,COLS,FRAMES=360,480,6,30
TINTS={'periodic':[.58,.81,1], 'age':[1,.76,.34], 'uncertainty':[.76,.55,1]}

# (time, root height offset, yaw, relative joint angles). Smooth interpolation
# between authored game poses; this is not a physics or locomotion controller.
def arms(l,r,le,re,lp=0,rp=0):
    return {'left_shoulder_roll_joint':l,'right_shoulder_roll_joint':r,
            'left_elbow_joint':le,'right_elbow_joint':re,
            'left_shoulder_pitch_joint':lp,'right_shoulder_pitch_joint':rp}
def crouch():
    return {'left_hip_pitch_joint':-.22,'right_hip_pitch_joint':-.22,
            'left_knee_joint':.44,'right_knee_joint':.44,
            'left_ankle_pitch_joint':-.22,'right_ankle_pitch_joint':-.22}
MOTIONS={
 'periodic':[(0,0,0,{}),(.18,-.10,0,{**crouch(),**arms(.1,-.1,-.25,-.25)}),
             (.36,.20,math.pi*.5,arms(.38,-.38,.2,.2)),
             (.55,.31,math.pi,arms(.45,-.45,.25,.25)),
             (.72,.12,math.pi*1.65,arms(.35,-.35,.1,.1)),
             (.84,-.07,math.tau,{**crouch(),**arms(.1,-.1,0,0)}),
             (1,0,math.tau,{})],
 'age':[(0,0,0,{}),(.18,0,-.13,arms(.5,-.5,-.2,.2,-.25,.25)),
        (.38,.025,.15,arms(.85,-.85,.45,.45,-.6,-.6)),
        (.59,0,0,arms(.25,-.25,.35,.35,.1,.1)),
        (.76,.04,0,arms(.18,-.28,.25,.65,0,-1.65)),
        (1,0,0,{})],
 'uncertainty':[(0,0,0,{}),(.19,-.04,-.2,arms(.35,-.35,.5,.5,-.35,-.35)),
                (.40,.05,.2,arms(.8,-.8,.5,.5,-1.25,-1.25)),
                (.58,.08,0,arms(.4,-.4,.45,.45,-1.8,-1.8)),
                (.74,0,0,arms(.55,-.55,.3,.3,-1.0,-1.0)),(1,0,0,{})]
}
def sample(name,t):
    frames=MOTIONS[name]
    for (t0,z0,y0,a),(t1,z1,y1,b) in zip(frames,frames[1:]):
        if t<=t1:
            u=max(0,min(1,(t-t0)/(t1-t0)))
            u=u*u*(3-2*u)
            return z0+(z1-z0)*u,y0+(y1-y0)*u,{k:a.get(k,0)+(b.get(k,0)-a.get(k,0))*u for k in a.keys()|b.keys()}
    return frames[-1][1:]

def generate(out, motion=None):
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
    head.attrib.update(ambient='.55 .55 .55',diffuse='.95 .95 .95',specular='.45 .45 .45')
    wb=root.find('worldbody')
    for node in list(wb):
        if node.tag in ('light','camera'): wb.remove(node)
    for pos,direction in [('3 -4 5','-3 4 -4'),('3 4 3','-3 -4 -2'),('-3 0 4','3 0 -3')]:
        ET.SubElement(wb,'light',pos=pos,dir=direction,diffuse='.85 .85 .85',ambient='.20 .20 .20',castshadow='false')
    model=mj.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
    data=mj.MjData(model)
    key=mj.mj_name2id(model,mj.mjtObj.mjOBJ_KEY,'stand')
    root_joint=mj.mj_name2id(model,mj.mjtObj.mjOBJ_JOINT,'floating_base_joint')
    adr=int(model.jnt_qposadr[root_joint])
    original=model.geom_rgba.copy();materials=model.geom_matid.copy()
    camera=mj.MjvCamera();mj.mjv_defaultCamera(camera)
    camera.type=mj.mjtCamera.mjCAMERA_FREE
    camera.lookat[:]=(0,0,.82);camera.distance=2.85;camera.azimuth=150;camera.elevation=-8
    opt=mj.MjvOption();mj.mjv_defaultOption(opt);opt.sitegroup[:]=0
    opt.geomgroup[2]=1;opt.geomgroup[3]=0
    out.mkdir(parents=True,exist_ok=True)
    def save(name,rgb):
        path=out/name;tmp=out/(name+'.tmp')
        tmp.write_bytes(base64.b64decode(png(rgb)));tmp.replace(path)
    def pose(name,t=None):
        mj.mj_resetDataKeyframe(model,data,key)
        if t is not None:
            z,yaw,joints=sample(name,t)
            data.qpos[adr+2]+=z
            data.qpos[adr+3:adr+7]=(math.cos(yaw/2),0,0,math.sin(yaw/2))
            for joint,delta in joints.items():
                i=mj.mj_name2id(model,mj.mjtObj.mjOBJ_JOINT,joint)
                if i<0: continue
                q=int(model.jnt_qposadr[i]);v=data.qpos[q]+delta
                data.qpos[q]=np.clip(v,*model.jnt_range[i]) if model.jnt_limited[i] else v
        mj.mj_forward(model,data)
    with mj.Renderer(model,height=HEIGHT,width=WIDTH) as renderer:
        for name in ([motion] if motion else TINTS):
            tint=np.array(TINTS[name])
            model.geom_rgba[:]=original;model.geom_matid[:]=materials
            for idx in range(model.ngeom):
                if model.geom_group[idx]!=2 or model.geom_type[idx]!=mj.mjtGeom.mjGEOM_MESH: continue
                mat=int(materials[idx]);base=model.mat_rgba[mat,:3] if mat>=0 else original[idx,:3]
                model.geom_rgba[idx,:3]=np.maximum(base,.27) if np.mean(base)<.35 else np.clip(base*.30+tint*.70,0,1)
                model.geom_rgba[idx,3]=1;model.geom_matid[idx]=-1
            def render(t=None):
                pose(name,t)
                renderer.update_scene(data,camera=camera,scene_option=opt)
                return renderer.render()
            if not motion:
                save(name+'.png',render())
            else:
                sheet=np.zeros((HEIGHT*((FRAMES+COLS-1)//COLS),WIDTH*COLS,3),dtype=np.uint8)
                for i in range(FRAMES):
                    y,x=divmod(i,COLS)
                    sheet[y*HEIGHT:(y+1)*HEIGHT,x*WIDTH:(x+1)*WIDTH]=render(i/(FRAMES-1))
                save(name+'-motion.png',sheet)
if __name__=='__main__':
    generate(Path(sys.argv[1]),sys.argv[2] if len(sys.argv)>2 else None)
