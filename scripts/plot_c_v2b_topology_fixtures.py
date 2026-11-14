"""Plot representative deterministic synthetic public-memory graph fixtures."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'scripts'))
from run_c_v2b_topology_fixtures import fixtures, OUT
from spatial_memory.navigation import plan
from spatial_memory.topology_evi import analyze_public_topology

def main():
    chosen=['unique_start_goal_articulation','irrelevant_dead_end_articulation',
        'narrow_corridor_with_alternative_loop','multiple_serial_bottlenecks',
        'occupied_cell_clearing_shortcut','multiple_correlated_uncertain_cells']
    by_name={f['name']:f for f in fixtures()}
    panel=390; margin=18; cell=20; grid_size=15*cell
    canvas=Image.new('RGB',(3*panel,2*(panel+28)), '#f6f8fa')
    draw=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14)
    except OSError: font=ImageFont.load_default()
    colors={-1:'#dce8f0',0:'#e8f5fb',1:'#33475b'}
    for idx,name in enumerate(chosen):
        f=by_name[name]; g=f['grid']; s=f['start']; t=f['goal']
        col=idx%3;row=idx//3
        px=col*panel+(panel-grid_size)//2
        py=row*(panel+28)+44
        draw.text((col*panel+12,row*(panel+28)+10),name.replace('_',' '),font=font,fill='#172b3d')
        for gy in range(g.shape[0]):
            for gx in range(g.shape[1]):
                x0=px+gx*cell;y0=py+gy*cell
                draw.rectangle((x0,y0,x0+cell-1,y0+cell-1),fill=colors[int(g[gy,gx])],outline='#c2d0da',width=1)
        route=plan(g,s,t,'optimistic')
        if route:
            points=[(px+x*cell+cell//2,py+y*cell+cell//2) for x,y in route]
            draw.line(points,fill='#5aafc8',width=3)
        graph=analyze_public_topology(g,s,t,'optimistic')
        for x,y in graph['separating']:
            cx=px+x*cell+cell//2;cy=py+y*cell+cell//2
            draw.ellipse((cx-7,cy-7,cx+7,cy+7),outline='#18a8bd',width=2)
        x,y=f['annotated_cell']
        cx=px+x*cell+cell//2;cy=py+y*cell+cell//2
        draw.ellipse((cx-9,cy-9,cx+9,cy+9),outline='#e5a922',width=3)
        for point,color,radius in ((s,'#35a8d0',5),(t,'#e8ad37',7)):
            cx=px+point[0]*cell+cell//2;cy=py+point[1]*cell+cell//2
            draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),fill=color,outline='white',width=1)
    draw.text((14,2*panel+6),'Cyan rings: start-goal separators  |  Gold ring: fixture target  |  Blue line: public A* route',font=font,fill='#40596d')
    path=OUT/'topology_fixture_maps.png'
    canvas.save(path)
    print(path)

if __name__=='__main__':main()
