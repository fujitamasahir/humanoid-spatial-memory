"""Read-only stage/trajectory/safety+liveness analysis; no new episodes or rays."""
import sys,json,gzip,math
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import write,manifest,verify_manifest,sha
from safety_forensics_v1 import OUT,native,ARMS
ACTUAL=('after_emergency_sensor_sync','after_sensing_before_action','after_executed_action')
EXTENTS=(.21895483127720788,.32799709120295073)


def read(p):return json.loads(gzip.decompress(p.read_bytes()))


def incident_analysis(e,definition):
    active=False;onsets=[];minimum=[]
    for event in e['events']:
        if event['stage'] not in ACTUAL:continue
        contact=sum(event['counts'].values())>0
        if event['minimum_geom_separation_m'] is not None:minimum.append(event['minimum_geom_separation_m'])
        if contact and not active:
            step=event['step'];stage=event['stage']
            ref=next((x for x in e['events'] if x['step']==step and x['stage']=='after_advance_synchronized_reference'),None)
            cls='environment_motion_at_sensor_synchronization' if stage=='after_emergency_sensor_sync' and ref and sum(ref['counts'].values()) else 'executed_action_or_other_actual_state_change'
            onsets.append({'step':step,'stage':stage,'mechanism':cls,'counts':event['counts'],
               'proven_first_transition_unavoidable':definition.get('declared_contact_class','').startswith('first_transition') and step==1})
        active=contact
    return onsets,min(minimum) if minimum else None


def risky_proxy(position,yaw,action,centers,*,future=False):
    # Independent closed-form cardinal segment/point clearance, not candidate slab code.
    kind,value=action;target=tuple(value) if kind in ('move','sidestep','retreat') else tuple(position)
    final_yaw=(int(value)*math.pi/2) if kind=='turn' and future else yaw
    if kind=='turn' and not future:hx=hy=math.hypot(*EXTENTS)/.75
    else:
        c,s=abs(math.cos(final_yaw)),abs(math.sin(final_yaw));hx=(c*EXTENTS[0]+s*EXTENTS[1])/.75;hy=(s*EXTENTS[0]+c*EXTENTS[1])/.75
    hx+=.19/.75;hy+=.19/.75
    start=target if future else position
    for x,y in centers:
        dx=max(min(start[0],target[0])-x,0,x-max(start[0],target[0]))
        dy=max(min(start[1],target[1])-y,0,y-max(start[1],target[1]))
        if dx<=hx and dy<=hy:return True
    return False


def summarize(e,definition):
    m=e['metrics'];trace=e['trace']['steps'][1:];onsets,minimum=incident_analysis(e,definition)
    moves=Counter(f['action'][0] if f['action'] else 'none' for f in trace)
    interventions=unnecessary=no_visible=0;current_only_certificates=0
    for d in e['decisions']:
        if d['safety_result'] is None:continue
        interventions+=1;no_visible+=not bool(d['measurement']['visible_pedestrian_cells'])
        step=d['step'];selected=d['selected_before'] or ('wait','no_base_action');program=definition['pedestrians']
        centers=lambda t:[p[t%len(p)] for p in program]
        clear=not risky_proxy(d['position'],d['yaw'],selected,centers(step))
        clear=clear and all(not risky_proxy(d['position'],d['yaw'],selected,centers(step+h),future=True) for h in (1,2))
        unnecessary+=clear
    idle=sum(moves[k] for k in ('none','wait'));terminal_idle=0
    for f in reversed(trace):
        if f['action'] is None or f['action'][0]=='wait':terminal_idle+=1
        else:break
    no_cert=sum(x['no_certifiably_safe_action'] for x in e['candidate_diagnostics'])
    sweep_hyp=[x for x in e['events'] if x['stage']=='selected_action_sweep_hypothesis']
    return {'scene':e['scene'],'role':e.get('role',definition.get('role','forensics')),'arm':e['arm'],'safety':e['safety'],
        'goals':int(m['success']),'contact_free_goal':int(m['success'] and not onsets),
        'contact_pairs':int(m['g1_unwanted_contact_pairs']),'post_action_contact_states':int(m['g1_unwanted_contact_states']),
        'distinct_actual_contact_episodes':len(onsets),'onsets':onsets,'minimum_pedestrian_geom_separation_m':minimum,
        'proven_unavoidable_first_onsets':sum(x['proven_first_transition_unavoidable'] for x in onsets),
        'other_onsets_not_proven_unavoidable':sum(not x['proven_first_transition_unavoidable'] for x in onsets),
        'blocked_actions':int(m['g1_footprint_blocked_attempts']),'rejected_selected_actions':int(m['g1_rejected_action_attempts']),
        'wait_actions':moves['wait'],'idle_steps':idle,'terminal_idle_run':terminal_idle,'sidesteps':moves['sidestep'],'retreats':moves['retreat'],
        'no_certifiably_safe_action':no_cert,'interventions':interventions,'geometric_unnecessary_proxy':unnecessary,
        'interventions_without_current_visible_hit':no_visible,'paid_scans':e['actual_calls']['memory'],
        'emergency_scans':e['actual_calls']['emergency'],'paid_rays':61*e['actual_calls']['memory'],
        'emergency_rays':61*e['actual_calls']['emergency'],'combined_rays':61*(e['actual_calls']['memory']+e['actual_calls']['emergency']),
        'actual_selected_shield_calls':e['actual_calls']['shield'],'selected_sweep_samples':len(sweep_hyp),
        'rejected_hypothetical_contact_samples':sum(bool(sum(x['counts'].values())) and x['sweep_actuality']=='rejected_hypothesis' for x in sweep_hyp),
        'steps':int(m['elapsed_steps']),'distance_m':float(m['travel_distance_m']),
        'safety_ms':sum(d['safety_ns'] for d in e['decisions'])/1e6,'wall_seconds':m['episode_wall_time_seconds']}


def main():
    target=OUT/'analysis';target.mkdir(parents=True,exist_ok=False)
    verify_manifest(OUT/'matrix');verify_manifest(OUT/'forensics')
    definitions=json.loads((OUT/'prepared/scenarios.json').read_text());rows=[];episodes={}
    for p in sorted((OUT/'matrix').glob('*.json.gz')):
        e=read(p);n=int(p.name.split('_')[0]);d=definitions[n-1];r=summarize(e,d);r['scene_index']=n
        assert e['actual_calls']['memory']==len(e['paid'])==e['metrics']['observation_count']<=20
        assert e['actual_calls']['emergency']==e['metrics']['emergency_safety_scans']
        assert e['actual_calls']['shield']==e['metrics']['g1_actual_collision_shield_queries'] and e['metrics']['g1_shield_query_count_valid']
        assert e['metrics']['g1_unselected_action_shield_queries']==0
        rows.append(r);episodes[n,e['arm'],e['safety']]=e
    assert len(rows)==416
    paired=[]
    for n,d in enumerate(definitions,1):
        for arm in ARMS:
            a=next(r for r in rows if (r['scene_index'],r['arm'],r['safety'])==(n,arm,'original'))
            b=next(r for r in rows if (r['scene_index'],r['arm'],r['safety'])==(n,arm,'predictive_v1'))
            paired.append({'scene_index':n,'scene':d['family'],'role':d['role'],'arm':arm,
                'original_goal':a['goals'],'candidate_goal':b['goals'],'rescued':b['goals']>a['goals'],'harmed':b['goals']<a['goals'],
                'new_contact_case':a['distinct_actual_contact_episodes']==0 and b['distinct_actual_contact_episodes']>0,
                'removed_contact_case':a['distinct_actual_contact_episodes']>0 and b['distinct_actual_contact_episodes']==0,
                'steps_delta_common_success':b['steps']-a['steps'] if a['goals'] and b['goals'] else None,
                'distance_delta_common_success':b['distance_m']-a['distance_m'] if a['goals'] and b['goals'] else None,
                'paid_delta':b['paid_scans']-a['paid_scans'],'combined_rays_delta':b['combined_rays']-a['combined_rays']})
    sum_keys=('goals','contact_free_goal','contact_pairs','post_action_contact_states','distinct_actual_contact_episodes',
       'proven_unavoidable_first_onsets','other_onsets_not_proven_unavoidable','blocked_actions','rejected_selected_actions',
       'wait_actions','idle_steps','sidesteps','retreats','no_certifiably_safe_action','interventions','geometric_unnecessary_proxy',
       'interventions_without_current_visible_hit','paid_scans','emergency_scans','paid_rays','emergency_rays','combined_rays',
       'actual_selected_shield_calls','selected_sweep_samples','rejected_hypothetical_contact_samples','steps','distance_m','safety_ms','wall_seconds')
    totals=[];by_scene=[];by_arm=[]
    for collection,keys in [(totals,('role','safety')),(by_scene,('role','scene','safety')),(by_arm,('role','arm','safety'))]:
        groups=defaultdict(list)
        for r in rows:groups[tuple(r[k] for k in keys)].append(r)
        for key,values in sorted(groups.items()):
            record={**dict(zip(keys,key)),'episodes':len(values),**{k:sum(r[k] for r in values) for k in sum_keys}}
            vals=[r['minimum_pedestrian_geom_separation_m'] for r in values if r['minimum_pedestrian_geom_separation_m'] is not None]
            record['minimum_pedestrian_geom_separation_m']=min(vals) if vals else None
            record['unnecessary_intervention_proxy_rate']=record['geometric_unnecessary_proxy']/record['interventions'] if record['interventions'] else None
            record['no_certifiable_action_per_step']=record['no_certifiably_safe_action']/record['steps'] if record['steps'] else None
            collection.append(record)
    new_contact=[p for p in paired if p['new_contact_case']];harms=[p for p in paired if p['harmed']]
    negative=[p for p in paired if p['role']=='prospective_benchmark' and p['scene'].startswith('no_pedestrian')]
    for p in negative:
        n,arm=p['scene_index'],p['arm'];assert episodes[n,arm,'original']['trace']==episodes[n,arm,'predictive_v1']['trace']
    write(target/'episode_metrics.json',rows);write(target/'paired.json',paired)
    write(target/'summary.json',{'decision':'REJECT_CANDIDATE_COMMON_REPLACEMENT','formal_episodes':416,'totals':totals,'by_scene':by_scene,'by_arm':by_arm,
       'new_contact_cases':new_contact,'goal_harms':harms,'negative_control_exact_trace_pairs':len(negative),
       'parameters_tuned_after_outcomes':False,'contact_episode_definition':'positive onset in chronological actual synchronized/preaction/postaction events; shadow and rejected sweep samples excluded',
       'unavoidable_scope':'Only first transition into start before any action is proven unavoidable; subsequent repeated contacts NOT excused.',
       'unnecessary_proxy_definition':'Original selected current AABB sweep and next2 actual program endpoint positions retrospectively clear, not causal unnecessary intervention.'})
    # Every original forensic replay has its own trajectory/stage figure.
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    for path in sorted((OUT/'forensics').glob('*.json.gz')):
        e=read(path);fig,(ax,timeax)=plt.subplots(1,2,figsize=(11,4));trace=e['trace']['steps'];robot=np.array([f['position'] for f in trace]);ax.plot(robot[:,0],robot[:,1],'-o',ms=3,label='robot')
        post=[x for x in e['events'] if x['stage']=='after_executed_action'];ped=[]
        for event in post:
            if event['pedestrian_geom_positions_m']:
                v=next(iter(event['pedestrian_geom_positions_m'].values()));ped.append((v[0]/.75+7,v[1]/.75+7))
        if ped:ax.plot(*zip(*ped),'-s',ms=3,label='pedestrian current model')
        for frame in trace:
            if frame['contacts']['g1_pedestrian_contact_pairs']:ax.annotate(f"t{frame['step']}",frame['position'],color='red')
        for stage,label in [('after_advance_raw_unsynchronized','raw after advance'),('after_advance_synchronized_reference','synchronized shadow'),('after_emergency_sensor_sync','actual after sensor sync'),('after_executed_action','actual post action')]:
            ev=[x for x in e['events'] if x['stage']==stage];timeax.plot([x['step'] for x in ev],[x['counts']['pedestrian'] for x in ev],'-o',ms=2,label=label)
        ax.set_aspect('equal');ax.legend(fontsize=7);ax.set(xlabel='Grid x',ylabel='Grid y');timeax.set(xlabel='Discrete step',ylabel='Pedestrian contact pairs');timeax.legend(fontsize=7)
        fig.suptitle('Untreated contact forensic: '+e['arm']);fig.tight_layout();fig.savefig(target/f'forensic_{e["arm"]}.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    cases=sorted({r['scene'] for r in by_scene if r['role']=='prospective_benchmark'})
    for label,offset in [('original',-.2),('predictive_v1',.2)]:
        values=[next(r for r in by_scene if r['role']=='prospective_benchmark' and r['scene']==case and r['safety']==label) for case in cases]
        axes[0].bar(np.arange(len(cases))+offset,[r['post_action_contact_states'] for r in values],width=.4,label=label)
        axes[1].bar(np.arange(len(cases))+offset,[r['goals'] for r in values],width=.4,label=label)
    for ax in axes:ax.set_xticks(range(len(cases)),cases,rotation=65,ha='right');ax.legend(fontsize=8)
    axes[0].set_ylabel('Actual post-action contact states');axes[1].set_ylabel('Goals out of8 observation policies');fig.tight_layout();fig.savefig(target/'benchmark_contacts_liveness.png',dpi=170);plt.close(fig)
    manifest(target);print(json.dumps({'decision':'REJECT','totals':totals,'new_contact_pairs':len(new_contact),'goal_harms':len(harms)},indent=2))
if __name__=='__main__':main()
