"""Presentation-only rendering; never mutates the navigation model or data."""
import base64
import math
import struct
import zlib
import numpy as np

def png(rgb):
    h,w,_=rgb.shape
    def chunk(t,d):
        return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    raw=b''.join(b'\x00'+row.tobytes() for row in rgb)
    return base64.b64encode(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,1))+chunk(b'IEND',b'')).decode('ascii')

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
                self.camera.type=mj.mjtCamera.mjCAMERA_FIXED
                self.camera.fixedcamid=mj.mj_name2id(s.model,mj.mjtObj.mjOBJ_CAMERA,'overview')
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
            self.renderer.update_scene(self.data,camera=self.camera)
            return {'render_png':png(self.renderer.render())}
        except Exception as exc:
            self.error=type(exc).__name__+': '+str(exc)
            self.close()
            return {'render_error':self.error}
    def close(self):
        if self.renderer is not None:
            try: self.renderer.close()
            except Exception: pass
            self.renderer=None
