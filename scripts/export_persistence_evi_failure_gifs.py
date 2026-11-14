"""Create retrospective side-by-side top-down FIT72 trajectory GIFs.

Only admitted maze walls and saved/replayed agent outputs are displayed. Hidden
dynamic occupancy is intentionally omitted; these are explanatory replays.
"""
from __future__ import annotations
import gzip,json,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
os.environ.setdefault('MPLCONFIGDIR','/tmp/phase2_mplconfig')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle
import numpy as np
import phase2_mujoco_navigation as nav
FIT=ROOT/'results/phase2_mujoco/persistence_evi_fit72_restored_local_v1'
OUT=ROOT/'results/phase2_mujoco/persistence_evi_failure_analysis_v1'

def load(n,arm,cf=None):
    if cf:
        d=json.loads((OUT/'counterfactuals'/cf).read_text())
        return {'steps':d['trace']}
    return json.loads(gzip.decompress((FIT/f'episode_{n:03}_{arm}.json.gz').read_bytes()))['trace']

def render(case_id, world_suffix, schedule, panels, filename, title):
    payload=next(w for w in nav.admitted_worlds() if w['identity'].endswith(world_suffix))
    free={tuple(x) for x in payload['geometry']['free']}; width=payload['geometry']['width'];height=payload['geometry']['height']
    world=payload['world'];start=tuple(world['start']);goal=tuple(world['goal'])
    traces=[load(number,arm,cf) for number,arm,label,cf in panels]
    nframes=max(len(t['steps']) for t in traces)
    fig,axes=plt.subplots(1,len(panels),figsize=(5.2*len(panels),5),constrained_layout=True)
    if len(panels)==1:axes=[axes]
    artists=[]
    for ax,(number,arm,label,cf),trace in zip(axes,panels,traces):
        ax.set_facecolor('#eef3f4')
        for y in range(height):
            for x in range(width):
                if (x,y) not in free:
                    ax.add_patch(Rectangle((x-.5,y-.5),1,1,color='#293943',lw=0))
        ax.scatter(*start,s=130,c='#17b8dc',edgecolor='white',linewidth=1.2,zorder=7,marker='o',label='Start')
        ax.scatter(*goal,s=155,c='#e7ae36',edgecolor='white',linewidth=1.2,zorder=7,marker='*',label='Goal')
        ax.set_xlim(-.6,width-.4);ax.set_ylim(height-.4,-.6);ax.set_aspect('equal')
        ax.set_xticks([]);ax.set_yticks([]);ax.set_title(label,fontsize=12,weight='bold')
        ax.text(.02,.02,'Wall map only; dynamic ground truth omitted',transform=ax.transAxes,fontsize=7,color='#263238')
        trail,=ax.plot([],[],color='#39a6b2',lw=2.2,alpha=.8,zorder=3)
        robot,=ax.plot([],[],marker='o',ms=11,mec='white',mew=1.2,color='#20272c',zorder=9)
        arrow=ax.annotate('',xy=(0,0),xytext=(0,0),arrowprops={'arrowstyle':'-|>','color':'#263238','lw':2},zorder=10)
        scan=ax.scatter([],[],s=45,marker='v',c='#21aa75',edgecolors='white',linewidths=.5,zorder=8)
        blocked=ax.scatter([],[],s=70,marker='x',c='#e34242',linewidths=2,zorder=8)
        steptext=ax.text(.03,.96,'',transform=ax.transAxes,va='top',fontsize=9,bbox={'facecolor':'white','alpha':.8,'edgecolor':'none'})
        artists.append((trail,robot,arrow,scan,blocked,steptext,trace))
    fig.suptitle(title+' — saved kinematic trajectories',fontsize=14,weight='bold')
    def update(frame_no):
        out=[]
        for trail,robot,arrow,scan,blocked,steptext,trace in artists:
            fs=trace['steps'];f=fs[min(frame_no,len(fs)-1)]
            upto=fs[:min(frame_no+1,len(fs))]
            xs=[p['position'][0] for p in upto];ys=[p['position'][1] for p in upto]
            trail.set_data(xs,ys);robot.set_data([f['position'][0]],[f['position'][1]])
            yaw=float(f['heading_yaw']);x,y=f['position'];arrow.xy=(x+.65*np.cos(yaw),y+.65*np.sin(yaw));arrow.set_position((x,y))
            obs=[p['position'] for p in upto if p.get('observation_granted') and p['step']>0]
            scan.set_offsets(np.asarray(obs,dtype=float).reshape(-1,2) if obs else np.empty((0,2)))
            rej=[p['position'] for p in upto if p.get('blocked')]
            blocked.set_offsets(np.asarray(rej,dtype=float).reshape(-1,2) if rej else np.empty((0,2)))
            steptext.set_text(f"step {f['step']} | scans {f['observation_count']} | blocked {sum(p.get('blocked',False) for p in upto)}")
            out.extend((trail,robot,arrow,scan,blocked,steptext))
        return out
    anim=FuncAnimation(fig,update,frames=nframes,interval=125,blit=False,repeat=True)
    anim.save(OUT/filename,writer=PillowWriter(fps=8),dpi=95)
    plt.close(fig)

def main():
    render(33,'M:80030004',0,[
      (33,'age','Age baseline: goal reached',None),(33,'c_ternary','C-only frozen: deadline failure',None),
      (33,'c_ternary','C-only + real scan at first blocked action','case_033_c_ternary_extra_scan_at_selected_step.json')],
      'M80030004_s0_age_C_early_scan.gif','M80030004 / schedule 0')
    render(3,'BP:80010001',0,[
      (3,'age','Age baseline: goal reached',None),(3,'c_ternary','C-only frozen: deadline failure',None),
      (3,'c_ternary','C-only + real scan at first blocked action','case_003_c_ternary_extra_scan_at_selected_step.json')],
      'BP80010001_s0_age_C_early_scan.gif','BP80010001 / schedule 0')

if __name__=='__main__':main()
