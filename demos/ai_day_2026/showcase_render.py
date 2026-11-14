"""Presentation-only rendering; never mutates the navigation model or data."""
import base64
import math
import struct
import zlib
import numpy as np

def png(rgb):
    h,w,channels=rgb.shape
    if channels not in (3,4): raise ValueError('Expected RGB or RGBA')
    def chunk(t,d):
        return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    raw=b''.join(b'\x00'+row.tobytes() for row in rgb)
    return base64.b64encode(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6 if channels==4 else 2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,1))+chunk(b'IEND',b'')).decode('ascii')

class ShowcaseRenderer:
    def __init__(self,scene,strategy):
        self.scene=scene
        self.renderer=None
        self.error=None
        self.strategy=strategy
        self.phase=0
    def frame(self,frame):
        if self.error:
            return {'render_error':self.error}
        try:
            s=self.scene; mj=s.mj
            if self.renderer is None:
                self.renderer=mj.Renderer(s.model,height=360,width=480)
                self.data=mj.MjData(s.model)
                self.camera=mj.MjvCamera()
                mj.mjv_defaultCamera(self.camera)
                self.camera.type=mj.mjtCamera.mjCAMERA_FREE
                self.camera.lookat[:]=(0,0,0.5)
                self.camera.azimuth=90
                self.camera.elevation=-68
                self.camera.distance=max(s.scenario.width,s.scenario.height)*s.cell_size*1.65
                self.option=mj.MjvOption()
                mj.mjv_defaultOption(self.option)
                self.option.geomgroup[5]=1
                self.option.sitegroup[:]=0
            self.data.qpos[:]=s.data.qpos
            self.data.mocap_pos[:]=s.data.mocap_pos
            self.data.mocap_quat[:]=s.data.mocap_quat
            if frame.get('moved'):
                self.phase+=1
                for side,sign in [('left',1),('right',-1)]:
                    for joint,amplitude in [('hip_pitch',.18),('knee',.10),('shoulder_pitch',-.15)]:
                        idx=mj.mj_name2id(s.model,mj.mjtObj.mjOBJ_JOINT,side+'_'+joint+'_joint')
                        if idx>=0:
                            adr=int(s.model.jnt_qposadr[idx])
                            self.data.qpos[adr]+=sign*amplitude*math.sin(self.phase*1.7)
            mj.mj_forward(s.model,self.data)
            self.renderer.update_scene(self.data,camera=self.camera,scene_option=self.option)
            # Bright presentation-only lighting: modify the renderer's scene,
            # not MjModel / MjData used for navigation, sensors or collisions.
            sc=self.renderer.scene
            # Replace the concentrated key-light hotspot with a broad,
            # low-specular directional fill on the presentation scene only.
            for index,light in enumerate(sc.lights[:sc.nlight]):
                light.ambient[:]=(.48,.48,.48) if index==0 else (0,0,0)
                light.diffuse[:]=(.48,.48,.48) if index==0 else (0,0,0)
                light.specular[:]=0
                light.castshadow=0
                if index==0:
                    if hasattr(light,'directional'):
                        light.directional=1
                    elif hasattr(light,'type') and hasattr(mj,'mjtLightType'):
                        directional=getattr(mj.mjtLightType,'mjLIGHT_DIRECTIONAL',None)
                        if directional is not None: light.type=directional
                    light.dir[:]=(.22,.32,-.92)
                    light.attenuation[:]=(1,0,0)
                    light.cutoff=180
            for geom in sc.geoms[:sc.ngeom]:
                if geom.objtype!=mj.mjtObj.mjOBJ_GEOM: continue
                gid=int(geom.objid)
                if gid in s._wall_geom_ids:
                    geom.rgba[:3]=(.62,.68,.76)
                elif gid==s._floor_geom_id:
                    geom.rgba[:3]=(.72,.76,.80)
                elif gid in s._object_geom_ids.values():
                    geom.rgba[:3]=(.95,.52,.18)
                elif gid in s._ped_geom_ids:
                    geom.rgba[:3]=(.95,.24,.33)
            gx,gy=s.grid_to_world(s.scenario.goal)
            sc=self.renderer.scene
            if sc.ngeom+2<=sc.maxgeom:
                for typ,size,pos,rgba in [
                    (mj.mjtGeom.mjGEOM_CYLINDER,[.28,.28,.035],[gx,gy,.04],[1,.65,.06,1]),
                    (mj.mjtGeom.mjGEOM_SPHERE,[.19,.19,.19],[gx,gy,1.1],[1,.8,.12,1])]:
                    mj.mjv_initGeom(sc.geoms[sc.ngeom],typ,np.array(size),np.array(pos),np.eye(3).ravel(),np.array(rgba,dtype=np.float32))
                    sc.ngeom+=1
            rgb=self.renderer.render()
            # Lift remaining shadow detail in the presentation image.
            rgb=np.asarray(255*np.power(rgb.astype(np.float32)/255,.92),dtype=np.uint8)
            return {'render_png':png(rgb)}
        except Exception as exc:
            self.error=type(exc).__name__+': '+str(exc)
            self.close()
            return {'render_error':self.error}
    def close(self):
        if self.renderer is not None:
            try: self.renderer.close()
            except Exception: pass
            self.renderer=None
