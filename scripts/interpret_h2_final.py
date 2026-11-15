"""Post-outcome interpretation and illustrative contrasts; no model execution.

Preserves original automatic analysis/report; final canonical report is copied
into a new interpretation stage. Extra examples are explicitly posthoc.
"""
import json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from h2_final_common import *
from h2_generate_maps import raster

def main():
    verify_manifest(OUT/'analysis');target=OUT/'interpretation';target.mkdir(exist_ok=False)
    data=json.loads((OUT/'analysis/summary.json').read_text());ss=data['summary'];records=[];exact={}
    for a in ('caa_full','caa_fast','raa_defer'):
        same=0
        for n in range(1,73):
            p=episode(OUT/'primary',n,'age5');c=episode(OUT/'primary',n,a)
            same+=p['trace']['steps']==c['trace']['steps']
            if p['diagnostics']['actual_memory_call_steps']!=c['diagnostics']['actual_memory_call_steps']:
                records.append({'candidate':a,'episode':n,'identity':p['row']['world_identity'],'schedule':p['row']['schedule'],'parent_success':p['row']['success'],'candidate_success':c['row']['success'],'parent_paid':p['row']['observation_count'],'candidate_paid':c['row']['observation_count'],'parent_scan_steps':p['diagnostics']['actual_memory_call_steps'],'candidate_scan_steps':c['diagnostics']['actual_memory_call_steps'],'parent_distance_m':p['row']['travel_distance_m'],'candidate_distance_m':c['row']['travel_distance_m']})
        exact[a]=same
    assert exact=={'caa_full':70,'caa_fast':71,'raa_defer':72}
    assert all(not r['parent_success'] and not r['candidate_success'] for r in records)
    write(target/'scan_difference_audit.json',{'exact_full_step_trace_matches_Age5':exact,'changed_scan_timing_cases':records,'CAA_savings_only_in_failed_episodes':True,'RAA_all72_exact_observable_step_traces_equal_Age5':True})
    # Illustrative additions requested by owner: first discordant outcome, fixed
    # lexicographic case rule. These examples were not a prospective efficacy test.
    examples=[]
    for a,b in (('periodic5','age5'),('rdao_v2','periodic5'),('rdao_v21','periodic5')):
        flips=[n for n in range(1,73) if episode(OUT/'primary',n,a)['row']['success']!=episode(OUT/'primary',n,b)['row']['success']]
        if not flips:continue
        n=flips[0];ident=episode(OUT/'primary',n,a)['row']['world_identity']
        maps=json.loads((OUT/'maps/summary.json').read_text())['maps'];p=next(json.loads((OUT/'maps'/r['path']).read_text()) for r in maps if r['identity']==ident)
        fig,axs=plt.subplots(1,2,figsize=(12,5))
        for ax,arm in zip(axs,(b,a)):
            e=episode(OUT/'primary',n,arm);r=e['row'];steps=e['trace']['steps'];ax.imshow(raster(p['geometry']['free']),cmap='Greys',origin='lower',vmin=0,vmax=1)
            xy=np.array([f['position'] for f in steps]);ax.plot(xy[:,0],xy[:,1],color='purple',lw=1.8)
            scan=np.array([f['position'] for f in steps if f['observation_granted']]);ax.scatter(scan[:,0],scan[:,1],s=25,facecolors='none',edgecolors='deepskyblue')
            ax.scatter(*p['world']['start'],c='limegreen',marker='o',s=30);ax.scatter(*p['world']['goal'],c='crimson',marker='*',s=70)
            ax.set_title(f'{arm} | goal {int(r["success"])} / paid {r["observation_count"]} / steps {r["elapsed_steps"]}');ax.set_xticks([]);ax.set_yticks([])
        fig.suptitle(f'Case{n:02} | first outcome discordance | posthoc descriptive example')
        name=f'contrast_{n:02}_{a}_vs_{b}';fig.savefig(target/(name+'.png'),bbox_inches='tight',dpi=180);fig.savefig(target/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
        examples.append({'episode':n,'candidate':a,'reference':b,'selection':'Posthoc illustrative; first case in frozen order with discordant success','figure':name+'.png'})
    write(target/'illustrative_examples.json',examples)
    actual=[]
    for a in ('caa_full','raa_defer'):
        for b in ('periodic4','periodic5','age4','age5'):
            costs=lambda arm:sum(ss[arm][k+'_total'] for k in ('decision_ms','update_ms','initialization_ms','memory_sensor_ms'))
            actual.append({'candidate':a,'reference':b,'measured_primary_observation_related_ms_delta':costs(a)-costs(b),'primary_wall_seconds_delta':ss[a]['wall_s_total']-ss[b]['wall_s_total'],'interpretation':'Measured simulation only; no energy or causal isolated scan-cost claim'})
    write(target/'measured_observation_cost_contrasts.json',actual)
    text=(ROOT/'docs/h2_final_research_report.md').read_text()
    abstract='''The best observed completion is Periodic-5 (60/72,661 paid readings,0contacts). RDAO v2 reaches59/72 with628 readings but incurs much higher compute. CAA-Full's three-scan aggregate saving over Age5 occurs only in two FAILED episodes; there is no successful-episode sensing or movement gain. RAA-Defer exactly matches Age5's observable traces in all72 cases and saves no scans. Thus the small FIT adaptive benefit does not establish a practically superior adaptive policy. A simple periodic clock is the leading practical default on this sample, with uncertainty and map-family tradeoffs.\n\n'''
    text=text.replace('## Motivation and research questions',abstract+'## Motivation and research questions',1)
    final='''## Final H2 conclusion and future directions

**H2 ends with no robust practical dominance of the complex adaptive schedulers.** Periodic-5 has the highest observed completion (60/72 versus59 for Age4/RDAO v2,57 for Age5/CAA-Full/RAA-Defer), with661 paid readings and zero contacts. Its success advantage over Age5 is only3 cases; the whole-lineage95% success-difference interval[-0.02778,0.125] includes zero. Its paid-reading difference interval[-1.93056,-0.93021] per case favors fewer readings on this conditional sample. This is a practical descriptive recommendation, not a general superiority/noninferiority proof.

Age4 remains useful where lower elapsed steps, combined rays and local runtime matter:59 goals,808 paid,223260combined rays and2852H80 steps versus Periodic5's60/661/227225/3064. The extra completion and fewer paid readings do not imply that Periodic5 dominates total sensing/movement cost. RDAO v2 is the sensing-oriented alternative (59 goals/628 paid/221552combined rays), but its primary decision cost31.215s and wall43.909s across72 cases far exceed Periodic5's0.164s and11.754s. RDAO v2.1 reduces paid readings further to550 while falling to56 goals and adding computation; it is a tradeoff, not the winner.

CAA-Full's57 goals/760 readings versus Age5's57/763 is only an aggregate count saving in two failed cases; common-success paid/steps/distance deltas are zero. Its paired paid95% interval[-0.11111,0] includes zero. Its higher fixed observation-related cost requires an assumed scan latency above22.664ms to break even against Age5, compared with a pooled measured simulator scan0.5943ms. No robust end-to-end advantage or energy saving is established. RAA-Defer's development terminal-saving signal vanishes: all72 step traces equal Age5,763 readings each, with extra decision cost and no nonnegative scan-price break-even against Age5. These are valuable negative generalization results.

Family results favor no hidden-family oracle: BP has23/24 goals for several models, while M is harder; Periodic5 and RDAO v2 reach19/24 M goals versus17 for Age4/Age5. In R, Periodic5/Age4 reach19/24 while RDAO v2/Age5 reach17. These small12-map family strata are descriptive, not a validated routing rule. The posthoc all-model success union67/72 is unattainable without outcome labels.

Freeze these outcomes and close H2 without model improvement, retuning or additional seed exploration. Further studies of calibrated visibility/value, longer continuing routes, independent custody or real-robot latency/energy would be separate future work requiring a new protocol. The current36-map, admission-conditioned, same-investigator/same-machine study does not prove equivalence, physical humanoid safety or universal generalization.

'''
    start=text.index('## Final H2 conclusion and future directions');end=text.index('## Artifacts and reproduction',start);text=text[:start]+final+text[end:]
    supplement=['','## Final trace audit and illustrative additions','',
    'The finalized trace audit was performed after the frozen primary/repeat matrix, without executing or modifying a scheduler. RAA-Defer and Age5 have exactly equal full observable step traces in72/72 cases. CAA-Full differs only in cases13(R:910000017,s0) and48(BP:910010012,s1), both failures for both policies: paid18→16 and20→19. CAA-Fast differs only in case48. All57 common successes preserve the same scan counts and movement; Full\'s0.75m all-case distance difference also comes from failures. The data therefore do not support successful-task improvement from CAA\'s tiny aggregate saving.','',
    'The two original prospectively selected CAA/RAA illustrations remain in analysis/. RAA\'s first case is an explicit null example because every paid difference is zero. Additional images below use a POSTHOC first-discordant-case rule for Periodic5/RDAO comparisons, to make the observed navigation differences visible. These figures illustrate, rather than establish causality or improve, the frozen aggregate findings.','',
    *[f'![Descriptive case{e["episode"]}](../results/phase2_mujoco/h2_final_generalization_v1/interpretation/{e["figure"]})' for e in examples],'',
    'Measured observation-related cost differences (decision+refresh+initialization+actual memory sensing; primary totals):','',
    '| Candidate | Reference | Delta ms | Wall delta seconds |','|---|---|---:|---:|',
    *[f'|{v["candidate"]}|{v["reference"]}|{v["measured_primary_observation_related_ms_delta"]:+.4f}|{v["primary_wall_seconds_delta"]:+.4f}|' for v in actual],'',
    'The original automatic analysis/report is retained byte-for-byte. This finalized report is stored in interpretation/final_research_report.md and docs/h2_final_research_report.md. Reproduction adds interpret_h2_final.py after report_h2_final.py. The separate backend-restoration amendment and failed setup are retained; the restoration was committed before any new draw.']
    text+='\n'.join(supplement)+'\n';(ROOT/'docs/h2_final_research_report.md').write_text(text);(target/'final_research_report.md').write_text(text);manifest(target)
    print('Final interpretation: Periodic5 practical leader; CAA savings failure-only; RAA=Age5 all72; no model changed.')
if __name__=='__main__':main()
