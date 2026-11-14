"""Generate portraits from pinned G1 meshes, outside the research simulation."""
import sys, base64
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco as mj
from showcase_render import png
ROOT=Path(__file__).resolve().parents[2]
def generate(out):
    src=ROOT/'third_party/unitree_g1/g1.xml'
    root=ET.parse(src).getroot()
    root.find('compiler').set('meshdir',str(src.parent/'assets'))
    wb=root.find('worldbody')
    for x in list(wb):
        if x.tag in ('light','camera'): wb.remove(x)
    for pos,diff in [('3 -4 5','1 .96 .9'),('1 4 3','.45 .55 .9'),('-3 0 4','.65 .65 .8')]:
        ET.SubElement(wb,'light',pos=pos,dir='-0.2 0 -1',diffuse=diff)
    model=mj.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
    data=mj.MjData(model)
    key=mj.mj_name2id(model,mj.mjtObj.mjOBJ_KEY,'stand')
    original=model.geom_rgba.copy()
    camera=mj.MjvCamera();mj.mjv_defaultCamera(camera)
    camera.type=mj.mjtCamera.mjCAMERA_FREE
    camera.lookat[:]=(0,0,.65);camera.distance=2.6;camera.azimuth=150;camera.elevation=-8
    opt=mj.MjvOption();mj.mjv_defaultOption(opt);opt.sitegroup[:]=0
    opt.geomgroup[2]=1
    out.mkdir(parents=True,exist_ok=True)
    with mj.Renderer(model,height=640,width=480) as renderer:
        for name,tint,pose in [('periodic',[.65,.84,1],{}),('age',[1,.69,.25],{'right_shoulder_roll_joint':-.48,'right_elbow_joint':.55}),('uncertainty',[.73,.48,1],{'left_shoulder_roll_joint':.42,'right_shoulder_roll_joint':-.42,'left_elbow_joint':.55,'right_elbow_joint':.55})]:
            mj.mj_resetDataKeyframe(model,data,key)
            model.geom_rgba[:]=original
            for idx in range(model.ngeom):
                if model.geom_type[idx]==mj.mjtGeom.mjGEOM_MESH:
                    model.geom_rgba[idx,:3]=np.clip(original[idx,:3]*.4+np.array(tint)*.6,0,1)
                    model.geom_matid[idx]=-1
            for joint,delta in pose.items():
                i=mj.mj_name2id(model,mj.mjtObj.mjOBJ_JOINT,joint)
                if i>=0:
                    adr=model.jnt_qposadr[i]
                    data.qpos[adr]=np.clip(data.qpos[adr]+delta,*model.jnt_range[i]) if model.jnt_limited[i] else data.qpos[adr]+delta
            mj.mj_forward(model,data)
            renderer.update_scene(data,camera=camera,scene_option=opt)
            (out/(name+'.png')).write_bytes(base64.b64decode(png(renderer.render())))
if __name__=='__main__':
    generate(Path(sys.argv[1]))
