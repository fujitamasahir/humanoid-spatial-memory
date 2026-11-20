"""Read-only reporting of frozen DAO mechanism outputs and planning arithmetic."""
from __future__ import annotations
import json, math, platform, sys
from pathlib import Path
from statistics import NormalDist
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from c_v21_common import write, manifest, verify_manifest, sha
OUT=ROOT/'results/phase2_mujoco/dao_v1'


def main():
    verify_manifest(OUT/'synthetic');verify_manifest(OUT/'retrospective')
    target=OUT/'analysis';target.mkdir(parents=True,exist_ok=False)
    rows=json.loads((OUT/'synthetic/decisions.json').read_text());summary=json.loads((OUT/'synthetic/summary.json').read_text())
    modes=list(dict.fromkeys(r['mode'] for r in rows));families=list(dict.fromkeys(r['family'] for r in rows))
    counts={mode:{'requests':sum(r['requested'] for r in rows if r['mode']==mode),
        'fallback_requests':sum(r['requested'] and r['fallback'] for r in rows if r['mode']==mode),
        'earlier_than_anchor':sum(r['requested'] and not r['age5_anchor'] for r in rows if r['mode']==mode),
        'vetoed_anchor':sum(not r['requested'] and r['age5_anchor'] for r in rows if r['mode']==mode)} for mode in modes}
    geometry=[{'family':r['family'], 'frontier_new':r['detail']['frontier']['new'],
        'optimistic_new':r['detail']['optimistic']['new'],
        'frontier_route_new':r['detail']['frontier']['route_new'],
        'samples':r['detail']['sample_visits']} for r in rows if r['step']==3 and r['mode']==modes[0]]
    z=NormalDist().inv_cdf(.975)+NormalDist().inv_cdf(.8)
    planning=[{'paired_lineage_sd':sd,'margin':margin,'true_difference':truth,
               'lineages_normal_approx':math.ceil((z*sd/(margin+truth))**2)}
        for sd in (.1,.15,.2,.3,.5) for margin in (.03,.10) for truth in (0.,-.01)]
    write(target/'planning.json',{'one_sided_alpha':.025,'power':.8,'z_sum':z,
        'normal_approximation':planning,'sd_ceiling_200_for_3point_NI':.03*math.sqrt(200)/z,
        'zero_contacts_200_lineages_upper95':1-.05**(1/200),
        'not_a_generation_or_power_guarantee':True,'runtime':{'python':sys.version,'platform':platform.platform(),'numpy':np.__version__}})
    write(target/'mechanisms.json',{'counts':counts,'geometry_at_t3':geometry,
        'formal_status':summary['status'],'source_freeze_commit':summary['source_freeze_commit'],
        'negative_findings':['No navigation efficacy measured.','Counts are not calibrated expected information gain.',
            'Conservative first-unknown stopping can miss deep corridor discovery.',
            'Fallback can request repeatedly for invisible stale cells until cap.',
            'Route relevance is a point-route proxy, not actual navigation value.']})
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(13,5));ys=np.arange(len(geometry))
    axes[0].barh(ys-.18,[g['frontier_new'] for g in geometry],height=.36,label='first-unknown frontier')
    axes[0].barh(ys+.18,[g['optimistic_new'] for g in geometry],height=.36,label='optimistic public raster')
    axes[0].set_yticks(ys,[g['family'] for g in geometry]);axes[0].set_xlabel('Predicted distinct unknown cells (not readings)');axes[0].legend()
    mat=np.array([[sum(r['requested'] for r in rows if r['family']==family and r['mode']==mode) for mode in modes] for family in families])
    im=axes[1].imshow(mat,vmin=0,vmax=4,cmap='Blues',aspect='auto');axes[1].set_xticks(range(len(modes)),modes,rotation=65,ha='right');axes[1].set_yticks(range(len(families)),families)
    for y in range(len(families)):
        for x in range(len(modes)):axes[1].text(x,y,str(mat[y,x]),ha='center',va='center',color='white' if mat[y,x]>=3 else 'black')
    axes[1].set_title('Requests in four same-geometry ages (0–4)');fig.colorbar(im,ax=axes[1]);fig.tight_layout();fig.savefig(target/'mechanisms.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4));sds=np.linspace(.05,.5,100)
    for margin in (.03,.10):ax.plot(sds,(z*sds/margin)**2,label=f'{100*margin:g}-point margin/effect, true difference 0')
    ax.axhline(200,color='gray',ls='--',label='provisional 200 lineages');ax.set(xlabel='SD of paired lineage-level difference',ylabel='Normal-approximate independent lineages',title='Planning sensitivity; not observed navigation power');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(target/'sample_size.png',dpi=170);plt.close(fig)
    manifest(target);print(json.dumps({'counts':counts,'geometry':geometry},indent=2))
if __name__=='__main__':main()
