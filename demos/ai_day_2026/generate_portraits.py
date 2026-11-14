"""Pre-render actual pinned G1 portraits and selection animations, offline."""
import sys, base64, math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco as mj
from showcase_render import png

ROOT=Path(__file__).resolve().parents[2]
WIDTH,HEIGHT,COLS,FRAMES=360,480,6,60
DEFEAT_DROP_FRAMES,DEFEAT_LOOP_FRAMES=30,24
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

def smoothstep(t):
    t=float(np.clip(t,0,1))
    return t*t*(3-2*t)

def defeat_phase(frame):
    """One collapse followed by a phase-continuous sobbing loop."""
    if not 0 <= frame < DEFEAT_DROP_FRAMES+DEFEAT_LOOP_FRAMES:
        raise ValueError('Invalid defeat frame')
    if frame < DEFEAT_DROP_FRAMES:
        t=frame/(DEFEAT_DROP_FRAMES-1)
        return smoothstep(t/.48), smoothstep((t-.48)/.52), 0.0
    phase=(frame-DEFEAT_DROP_FRAMES)/DEFEAT_LOOP_FRAMES
    return 1.0,1.0,math.tau*phase

class DefeatChoreography:
    """Display-model-only kinematic contact choreography, not a physics controller."""
    def __init__(self,model,data,root_adr,key):
        self.model,self.data,self.root_adr=model,data,root_adr
        self.ids={}
        for i in range(model.njnt):
            name=mj.mj_id2name(model,mj.mjtObj.mjOBJ_JOINT,i)
            if name: self.ids[name]=i
        mj.mj_resetDataKeyframe(model,data,key);mj.mj_forward(model,data)
        self.stand=data.qpos.copy()
        self.meshes=[]
        # Use the actual visible knee/foot mesh lower bounds, not a guessed root height.
        for gid in range(model.ngeom):
            if model.geom_group[gid]!=2 or model.geom_type[gid]!=mj.mjtGeom.mjGEOM_MESH:
                continue
            mesh=int(model.geom_dataid[gid])
            name=mj.mj_id2name(model,mj.mjtObj.mjOBJ_MESH,mesh) or ''
            if not any(part in name for part in ('knee_link','ankle_pitch_link','ankle_roll_link')):
                continue
            adr,num=int(model.mesh_vertadr[mesh]),int(model.mesh_vertnum[mesh])
            self.meshes.append((gid,model.mesh_vert[adr:adr+num].copy()))
        self.floor=self.lowest()
        self.hand_bodies=[mj.mj_name2id(model,mj.mjtObj.mjOBJ_BODY,side+'_wrist_yaw_link')
                          for side in ('left','right')]
        self.shoulders=[mj.mj_name2id(model,mj.mjtObj.mjOBJ_BODY,side+'_shoulder_pitch_link')
                        for side in ('left','right')]
        if min(self.hand_bodies+self.shoulders)<0 or not self.meshes:
            raise ValueError('Pinned G1 defeat contact landmarks were not found')
        self.hand_local=np.array([.075,0,0])
        self.targets=None
        self.settled=None
        self.arm_anchors={}
        self.hand_orientation={}
        self.hand_clearance={}
        for side,body in zip(('left','right'),self.hand_bodies):
            gid=mj.mj_name2id(model,mj.mjtObj.mjOBJ_GEOM,side+'_open_showcase')
            if gid<0: raise ValueError('Showcase hand mesh missing: '+side)
            mesh=int(model.geom_dataid[gid])
            adr,num=int(model.mesh_vertadr[mesh]),int(model.mesh_vertnum[mesh])
            vertices=model.mesh_vert[adr:adr+num]
            world=vertices@data.geom_xmat[gid].reshape(3,3).T+data.geom_xpos[gid]
            local=(world-data.xpos[body])@data.xmat[body].reshape(3,3)
            lo,hi=np.quantile(local[:,0],[.05,.95])
            palm=local[(local[:,0]>=lo+.22*(hi-lo))&(local[:,0]<=lo+.61*(hi-lo))]
            tips=local[local[:,0]>=lo+.76*(hi-lo)]
            # Infer transverse palm normal from the fixed mesh thickness;
            # the curved fingertips indicate the palm-facing side.
            _,vec=np.linalg.eigh(np.cov(palm[:,1:].T))
            normal=np.array([0.,*vec[:,0]])
            if np.dot(tips.mean(axis=0)-palm.mean(axis=0),normal)<0: normal=-normal
            forward=np.array([1.,0.,0.])
            local_basis=np.column_stack((forward,np.cross(normal,forward),normal))
            world_basis=np.diag([1.,-1.,-1.])
            rotation=world_basis@local_basis.T
            self.hand_orientation[side]=rotation
            self.hand_clearance[side]=float(-np.min((local-self.hand_local)@rotation[2]))

    def lowest(self):
        if not self.meshes: return 0.0
        return min(float(np.min(vertices @ self.data.geom_xmat[gid].reshape(3,3)[2]
                                + self.data.geom_xpos[gid,2]))
                   for gid,vertices in self.meshes)

    def set_joint(self,name,value):
        idx=self.ids.get(name)
        if idx is None: return
        adr=int(self.model.jnt_qposadr[idx])
        if self.model.jnt_limited[idx]: value=np.clip(value,*self.model.jnt_range[idx])
        self.data.qpos[adr]=value

    def hand_pos(self,body):
        return self.data.xpos[body]+self.data.xmat[body].reshape(3,3)@self.hand_local

    def arm_indices(self,side):
        joint_names=[side+'_'+name+'_joint' for name in
                     ('shoulder_pitch','shoulder_roll','shoulder_yaw','elbow',
                      'wrist_roll','wrist_pitch','wrist_yaw')]
        return [self.ids[name] for name in joint_names if name in self.ids]

    def solve_hand(self,side,body,target,bow,orientation=None,precise=False):
        indices=self.arm_indices(side)
        dofs=[int(self.model.jnt_dofadr[i]) for i in indices]
        jacp=np.zeros((3,self.model.nv));jacr=np.zeros_like(jacp)
        desired=self.hand_orientation[side] if orientation is None else orientation
        weight=.27*bow
        position_tol=.00025 if precise else .002
        rotation_tol=.002 if precise else .035
        for _ in range(60 if precise else 55):
            pos=self.hand_pos(body)
            actual=self.data.xmat[body].reshape(3,3)
            error=target-pos
            quat=np.zeros(4);angular=np.zeros(3)
            mj.mju_mat2Quat(quat,(desired@actual.T).ravel())
            if quat[0]<0: quat=-quat
            mj.mju_quat2Vel(angular,quat,1.)
            if np.linalg.norm(error)<position_tol and (bow<.05 or np.linalg.norm(angular)<rotation_tol): break
            mj.mj_jac(self.model,self.data,jacp,jacr,pos,body)
            J=np.vstack((jacp[:,dofs],weight*jacr[:,dofs]))
            residual=np.concatenate((error,weight*angular))
            delta=J.T@np.linalg.solve(J@J.T+(.00008 if precise else .0015)*np.eye(6),residual)
            for i,dq in zip(indices,np.clip(delta,-.22,.22)):
                adr=int(self.model.jnt_qposadr[i])
                name=mj.mj_id2name(self.model,mj.mjtObj.mjOBJ_JOINT,i)
                self.set_joint(name,self.data.qpos[adr]+dq)
            mj.mj_forward(self.model,self.data)

    def tremble_arms(self,phase):
        """Arm self-motion in the planted-palm Jacobian null space.

        Base, knees and spine remain exactly at the settled pose. A correction
        restores the achieved palm position AND orientation; reject any frame
        that cannot preserve contact within the small visual tolerance.
        """
        m,d=self.model,self.data
        for side,body in zip(('left','right'),self.hand_bodies):
            indices=self.arm_indices(side)
            qadr=[int(m.jnt_qposadr[i]) for i in indices]
            dofs=[int(m.jnt_dofadr[i]) for i in indices]
            neutral=d.qpos[qadr].copy()
            target,orientation=self.arm_anchors[side]
            jacp=np.zeros((3,m.nv));jacr=np.zeros_like(jacp)
            mj.mj_jac(m,d,jacp,jacr,self.hand_pos(body),body)
            J=np.vstack((jacp[:,dofs],.27*jacr[:,dofs]))
            _,singular,Vt=np.linalg.svd(J,full_matrices=True)
            rank=int(np.count_nonzero(singular>1e-6))
            null=Vt[rank:].T
            if not null.size: continue
            # Favor elbow swivel / shoulder movement; wrist only compensates.
            preference=np.array([1. if 'shoulder_yaw' in (mj.mj_id2name(m,mj.mjtObj.mjOBJ_JOINT,i) or '')
                                 else .65 if 'elbow' in (mj.mj_id2name(m,mj.mjtObj.mjOBJ_JOINT,i) or '')
                                 else 0. for i in indices])
            delta=null@(null.T@preference)
            if np.linalg.norm(delta)<1e-7: delta=null[:,0]
            delta/=max(np.max(np.abs(delta)),1e-8)
            sign=1 if side=='left' else -1
            amplitude=sign*(.075*math.sin(3*phase)+.035*math.sin(5*phase))
            for factor in (1.,.5,.25):
                for i,value,shift in zip(indices,neutral,delta):
                    name=mj.mj_id2name(m,mj.mjtObj.mjOBJ_JOINT,i)
                    self.set_joint(name,value+factor*amplitude*shift)
                mj.mj_forward(m,d)
                self.solve_hand(side,body,target,1.,orientation=orientation,precise=True)
                pos_error=np.linalg.norm(self.hand_pos(body)-target)
                rot_error=np.linalg.norm(d.xmat[body].reshape(3,3)-orientation)
                if pos_error<=.0008 and rot_error<=.006:
                    break
            else:
                d.qpos[qadr]=neutral
                mj.mj_forward(m,d)

    def pose(self,kneel,bow,phase):
        m,d=self.model,self.data
        if kneel==1. and bow==1. and self.settled is not None:
            d.qpos[:]=self.settled
            mj.mj_forward(m,d)
            self.tremble_arms(phase)
            return
        d.qpos[:]=self.stand
        # G1 waist pitch is limited to +/- .52 radians. Combine the
        # pelvic pitch and waist pitch to make the torso horizontal.
        pitch=(math.pi/2-.51)*bow
        d.qpos[self.root_adr+3:self.root_adr+7]=(math.cos(pitch/2),0,math.sin(pitch/2),0)
        targets={}
        for side,sign in (('left',1),('right',-1)):
            targets.update({
                side+'_hip_pitch_joint':-.18-pitch,
                side+'_hip_roll_joint':sign*.07,
                side+'_hip_yaw_joint':0,
                side+'_knee_joint':2.14-.36*bow,
                side+'_ankle_pitch_joint':-.82,
                side+'_ankle_roll_joint':0,
                side+'_shoulder_pitch_joint':.18-1.77*bow,
                side+'_shoulder_roll_joint':sign*(.13+.025*bow),
                side+'_shoulder_yaw_joint':0,
                side+'_elbow_joint':1.36+.17*bow,
                side+'_wrist_pitch_joint':-.22*bow,
            })
        targets['waist_pitch_joint']=.51*bow
        targets['waist_roll_joint']=0.
        for name,target in targets.items():
            idx=self.ids.get(name)
            if idx is not None:
                orig=self.stand[int(m.jnt_qposadr[idx])]
                self.set_joint(name,orig+(target-orig)*kneel)
        mj.mj_forward(m,d)
        # Measure thigh direction from the real skeleton, not just joint
        # offsets. With the torso horizontal, vertical thighs form ~90°.
        if bow>0:
            for side in ('left','right'):
                hip=mj.mj_name2id(m,mj.mjtObj.mjOBJ_BODY,side+'_hip_pitch_link')
                knee=mj.mj_name2id(m,mj.mjtObj.mjOBJ_BODY,side+'_knee_link')
                name=side+'_hip_pitch_joint'
                q=int(m.jnt_qposadr[self.ids[name]])
                for _ in range(4):
                    v=d.xpos[knee]-d.xpos[hip]
                    correction=math.atan2(float(v[0]),float(-v[2]))
                    self.set_joint(name,d.qpos[q]+bow*correction)
                    mj.mj_forward(m,d)
        d.qpos[self.root_adr+2]+=self.floor-self.lowest()
        mj.mj_forward(m,d)
        if bow>0:
            # The palm targets settle on the common ground plane and remain
            # planted through the trembling cycle. Solve each arm independently.
            if self.targets is None:
                self.targets=[]
                for side,shoulder,sign in zip(('left','right'),self.shoulders,(1,-1)):
                    q=d.xpos[shoulder].copy()
                    q[0]+=.08
                    q[1]=sign*.19;q[2]=self.floor+self.hand_clearance[side]
                    self.targets.append(q)
            for side,body,target in zip(('left','right'),self.hand_bodies,self.targets):
                initial=self.hand_pos(body)
                self.solve_hand(side,body,initial*(1-bow)+target*bow,bow)
        if kneel==1. and bow==1.:
            self.settled=d.qpos.copy()
            self.arm_anchors={side:(self.hand_pos(body).copy(),d.xmat[body].reshape(3,3).copy())
                              for side,body in zip(('left','right'),self.hand_bodies)}

def generate(out, motion=None, reaction=None, still_strategy=None):
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
    defeat=DefeatChoreography(model,data,adr,key) if reaction=='defeat' else None
    if defeat is not None:
        defeat.pose(1,1,0)  # establish the planted palm targets at the final pose
    def pose(name,t=None):
        mj.mj_resetDataKeyframe(model,data,key)
        if defeat is not None:
            frame=DEFEAT_DROP_FRAMES if t is None else int(t)
            kneel,bow,phase=defeat_phase(frame)
            defeat.pose(kneel,bow,phase)
            camera.lookat[:]=(.12*bow,0,.62-.30*bow)
            camera.distance=2.25-.40*bow
            camera.azimuth=145;camera.elevation=-16-3*bow
            return
        if t is not None:
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
        for name in ([motion or still_strategy] if motion or still_strategy else TINTS):
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
                if motion:
                    total=DEFEAT_DROP_FRAMES+DEFEAT_LOOP_FRAMES
                    sheet=np.zeros((HEIGHT*((total+COLS-1)//COLS),WIDTH*COLS,4),dtype=np.uint8)
                    for i in range(total):
                        y,x=divmod(i,COLS)
                        sheet[y*HEIGHT:(y+1)*HEIGHT,x*WIDTH:(x+1)*WIDTH]=render(i)
                    save(name+'-defeat-motion-v13.png',sheet)
                else:
                    save(name+'-defeat-pose-v13.png',render())
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
             sys.argv[3] if len(sys.argv)>3 else None,
             sys.argv[4] if len(sys.argv)>4 else None)
