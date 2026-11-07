"""Frozen family/cap-balanced selection using exact rational arithmetic."""
from collections import defaultdict
from fractions import Fraction
from .tuning_spec import GRID,CAPS,SELECTION_VERSION,candidates


def select_parameters(rows):
    grouped=defaultdict(list)
    for row in rows:
        grouped[(row['method'],row['candidate'])].append(row)
    scores=[];selected={}
    for candidate in candidates():
        method,index=candidate['method'],candidate['candidate']
        episodes=grouped[(method,index)]
        strata=defaultdict(list)
        for r in episodes:
            strata[(r['family'],r['cap'])].append(r['metrics'])
        if len(episodes)!=105 or len(strata)!=21 or any(len(s)!=5 for s in strata.values()):
            raise ValueError('Incomplete/unbalanced candidate results')
        means={}
        for metric in ('contact_free_success','success','observation_count','elapsed_steps','observation_cost'):
            # Cost is exactly 3/2 times integer observation count, never a float tie-break.
            means[metric]=sum((sum((Fraction(m['observation_count'])*Fraction(3,2) if metric=='observation_cost'
                else Fraction(int(m[metric]))) for m in group)/len(group) for group in strata.values()),Fraction())/len(strata)
        key=(-means['contact_free_success'],-means['success'],means['observation_count'],
             means['elapsed_steps'],tuple(candidate['parameter_tuple']))
        score=dict(**candidate,episodes=105,means={k:float(v) for k,v in means.items()},
            exact_means={k:[v.numerator,v.denominator] for k,v in means.items()},
            selection_key=[str(k) if isinstance(k,Fraction) else list(k) for k in key])
        scores.append(score)
        if method not in selected or key<selected[method][0]:
            selected[method]=(key,score)
    if len(rows)!=3780:
        raise ValueError('Selection requires all 3780 prescribed episodes')
    return dict(version=SELECTION_VERSION,candidates=scores,
                selected={m:value[1] for m,value in selected.items()})
