'use strict';
const $=id=>document.getElementById(id);let catalog=[],mazeIndex=0,objects=[],pedestrians=[],strategy='periodic',tool='object',cursor=[1,1],cellGeom=null,latestFrame=-1,lastResult=null,lastConfig=null,gamepadPrev=new Set(),lastPadAction=0,ws;
const colors={wall:'#263647',free:'#101a26',unknown:'#5f6978',memoryFree:'#174247',memoryWall:'#60413a',object:'#f19a43',ped:'#f26970',cyan:'#49e0eb',gold:'#ffca63',robot:'#64b4ff'};
async function api(url,options={}){const r=await fetch(url,{headers:{'Content-Type':'application/json'},...options});let d=await r.json();if(!r.ok)throw Error(d.detail||d.error||`HTTP ${r.status}`);return d}
function toast(s){$('toast').textContent=s;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),2300)}
function current(){return catalog[mazeIndex]}
function setTool(t){tool=t;for(const [id,v] of [['objectTool','object'],['pedTool','ped'],['removeTool','remove']])$(id).classList.toggle('active',t===v)}
function dimensions(canvas,maze){const pad=30,scale=Math.min((canvas.width-pad*2)/maze.width,(canvas.height-pad*2)/maze.height);const w=scale*maze.width,h=scale*maze.height;return {x:(canvas.width-w)/2,y:(canvas.height-h)/2,scale,w,h}}
function drawMap(canvas,maze,{memory=null,objects:obs=[],peds=[],robot=null,trajectory=[],cursorCell=null,editor=false,northUp=false,observedObjects=[],observedPeople=[]}={}){const ctx=canvas.getContext('2d',{alpha:false});ctx.fillStyle='#0b111a';ctx.fillRect(0,0,canvas.width,canvas.height);const d=dimensions(canvas,maze);cellGeom=d;const displayY=y=>northUp?maze.height-1-y:y;for(let y=0;y<maze.height;y++)for(let x=0;x<maze.width;x++){const bit=maze.wall_rows[y][x],v=memory?memory[y][x]:null;const wallColor=({R:'#355c88',BP:'#76529b',M:'#327d70'}[maze.mechanism]||colors.wall);ctx.fillStyle=memory?(v<0?(bit==='1'?wallColor:colors.free):v===1?wallColor:colors.memoryFree):(bit==='1'?wallColor:colors.free);ctx.globalAlpha=memory&&v<0?.23:1;ctx.fillRect(d.x+x*d.scale,d.y+displayY(y)*d.scale,d.scale-.7,d.scale-.7);ctx.globalAlpha=1;if((!memory||v===1)&&bit==='1'){const X=d.x+x*d.scale,Y=d.y+displayY(y)*d.scale,z=d.scale;ctx.fillStyle='#ffffff25';ctx.fillRect(X,Y,z-.7,z*.16);ctx.fillStyle='#00000055';ctx.fillRect(X,Y+z*.72,z-.7,z*.28);ctx.fillRect(X+z*.78,Y,z*.22,z*.72)}if(!memory&&bit==='0'){ctx.fillStyle='#ffffff08';ctx.fillRect(d.x+x*d.scale+1,d.y+displayY(y)*d.scale+1,d.scale-2,d.scale-2)}}
const detected=(cells,x,y)=>cells.some(p=>p[0]===x&&p[1]===y);
for(const [x,y] of obs){ctx.globalAlpha=memory?(detected(observedObjects,x,y)?1:.23):1;ctx.fillStyle=colors.object;ctx.beginPath();ctx.roundRect(d.x+x*d.scale+d.scale*.19,d.y+displayY(y)*d.scale+d.scale*.19,d.scale*.62,d.scale*.62,3);ctx.fill();ctx.globalAlpha=1}
for(const [x,y] of peds){ctx.globalAlpha=memory?(detected(observedPeople,x,y)?1:.23):1;ctx.fillStyle=colors.ped;ctx.beginPath();ctx.arc(d.x+(x+.5)*d.scale,d.y+(displayY(y)+.5)*d.scale,d.scale*.3,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#ffd5d4';ctx.lineWidth=2;ctx.stroke();ctx.globalAlpha=1}
// Render the last detected pedestrian location at full opacity, even if the real person moved.
if(memory){for(const [x,y] of observedPeople){if(detected(peds,x,y))continue;ctx.globalAlpha=1;ctx.strokeStyle=colors.ped;ctx.lineWidth=2;ctx.beginPath();ctx.arc(d.x+(x+.5)*d.scale,d.y+(displayY(y)+.5)*d.scale,d.scale*.28,0,Math.PI*2);ctx.stroke()}}
const [sx,sy]=maze.start,[gx,gy]=maze.goal;ctx.save();ctx.translate(d.x+(sx+.5)*d.scale,d.y+(displayY(sy)+.5)*d.scale);ctx.scale(d.scale/20,d.scale/20);ctx.fillStyle='#a7d9ff';ctx.beginPath();ctx.roundRect(-4,-9,8,7,2);ctx.fill();ctx.fillRect(-5,-1,10,6);ctx.fillRect(-8,-1,2,7);ctx.fillRect(6,-1,2,7);ctx.fillRect(-4,5,3,5);ctx.fillRect(1,5,3,5);ctx.restore();ctx.save();ctx.translate(d.x+(gx+.5)*d.scale,d.y+(displayY(gy)+.5)*d.scale);const z=d.scale;ctx.shadowColor='#ffb72e';ctx.shadowBlur=z*.9;ctx.strokeStyle='#ffdc89';ctx.lineWidth=Math.max(1,z*.08);ctx.beginPath();ctx.ellipse(0,z*.26,z*.38,z*.14,0,0,Math.PI*2);ctx.stroke();ctx.fillStyle='#ffb932';ctx.beginPath();ctx.moveTo(0,z*.25);ctx.bezierCurveTo(-z*.7,-z*.48,-z*.23,-z*.75,0,-z*.75);ctx.bezierCurveTo(z*.55,-z*.75,z*.53,-z*.32,0,z*.25);ctx.fill();ctx.stroke();ctx.shadowBlur=0;ctx.fillStyle='#493017';ctx.beginPath();ctx.arc(0,-z*.36,z*.13,0,Math.PI*2);ctx.fill();ctx.restore();
if(trajectory.length>1){ctx.beginPath();trajectory.forEach((p,i)=>{const X=d.x+(p[0]+.5)*d.scale,Y=d.y+(displayY(p[1])+.5)*d.scale;i?ctx.lineTo(X,Y):ctx.moveTo(X,Y)});ctx.strokeStyle='#62bdffb0';ctx.lineWidth=Math.max(2,d.scale*.12);ctx.stroke()}
if(robot){const [x,y]=robot.position;const cx=d.x+(x+.5)*d.scale,cy=d.y+(displayY(y)+.5)*d.scale;ctx.save();ctx.translate(cx,cy);ctx.rotate((northUp?-1:1)*robot.heading_yaw);ctx.fillStyle=colors.robot;ctx.shadowColor=colors.robot;ctx.shadowBlur=d.scale*.8;ctx.beginPath();ctx.moveTo(d.scale*.4,0);ctx.lineTo(-d.scale*.25,-d.scale*.25);ctx.lineTo(-d.scale*.18,d.scale*.25);ctx.closePath();ctx.fill();ctx.restore()}
if(editor&&cursorCell){const[x,y]=cursorCell;ctx.strokeStyle='#eaf8ff';ctx.lineWidth=3;ctx.strokeRect(d.x+x*d.scale+1,d.y+displayY(y)*d.scale+1,d.scale-2,d.scale-2)} }
let stripIndex=-1;
function updateMazeStrip(){
 const strip=$('mazeStrip');
 if(!strip.children.length){
  catalog.forEach((m,index)=>{
   const button=document.createElement('button');button.type='button';button.title='Maze '+(index+1)+' · '+m.mechanism;
   button.setAttribute('aria-label',button.title);button.onclick=()=>setMaze(index);
   const canvas=document.createElement('canvas');canvas.width=m.width;canvas.height=m.height;
   const ctx=canvas.getContext('2d');ctx.fillStyle='#0c1622';ctx.fillRect(0,0,m.width,m.height);
   ctx.fillStyle=({R:'#659fe0',BP:'#a58be7',M:'#56c6aa'}[m.mechanism]||'#94a6b8');
   for(let y=0;y<m.height;y++)for(let x=0;x<m.width;x++)if(m.wall_rows[y][x]==='1')ctx.fillRect(x,m.height-1-y,1,1);
   button.append(canvas);strip.append(button);
  });
 }
 if(stripIndex===mazeIndex)return;stripIndex=mazeIndex;
 Array.from(strip.children).forEach((b,index)=>{b.classList.toggle('selected',index===mazeIndex);b.setAttribute('aria-pressed',String(index===mazeIndex))});
}
function inventoryIcon(object){
 return object?'<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M3 12L20 3L37 12L20 22Z" fill="#ffd18b" stroke="#bc813e"/><path d="M3 12L20 22V38L3 28Z" fill="#bd7632"/><path d="M20 22L37 12V28L20 38Z" fill="#805020"/><path d="M12 7L29 17V32" fill="none" stroke="#fff1bd" stroke-width="3" opacity=".7"/></svg>':'<svg viewBox="0 0 40 48" aria-hidden="true"><ellipse cx="20" cy="45" rx="13" ry="2" fill="#0005"/><circle cx="20" cy="8" r="6" fill="#f0b78d"/><path d="M14 15Q20 12 26 15L29 29H11Z" fill="#e47775"/><path d="M14 18L7 29M26 18L33 29" stroke="#f0b78d" stroke-width="5" stroke-linecap="round"/><path d="M16 28L14 43M24 28L26 43" stroke="#526b8a" stroke-width="7" stroke-linecap="round"/><path d="M11 44H16M24 44H30" stroke="#222e40" stroke-width="4" stroke-linecap="round"/><path d="M16 16L14 26" stroke="#ffaaa0" stroke-width="2"/></svg>';
}
function renderEditor(){const m=current();drawMap($('editorCanvas'),m,{northUp:true,objects,peds:pedestrians,editor:true,cursorCell:cursor});$('mazeIdentity').textContent=`MAZE ${String(mazeIndex+1).padStart(2,'0')} / ${catalog.length} · ${m.mechanism}`;updateMazeStrip();for(const [id,used,icon] of [['objectCount',objects.length,'◆'],['pedCount',pedestrians.length,'♟']]){const el=$(id);el.replaceChildren(...Array.from({length:Number(el.dataset.max)},(_,i)=>{const s=document.createElement('i');s.className=i<used?'spent':'';s.innerHTML=inventoryIcon(id==='objectCount');return s}))}}
async function validate(){const rev=revision;const v=await api('/api/validate',{method:'POST',body:JSON.stringify({maze_id:current().id,objects,pedestrians})});if(rev!==revision||editing)return v;const el=$('validation');el.textContent=v.valid?'LAYOUT VALID':v.errors.join(' ');el.classList.toggle('error',!v.valid);$('startBtn').disabled=!v.valid;return v}
function clearEdits(){objects=[];pedestrians=[];validate().catch(e=>toast(e.message));renderEditor()}
let editing=false,starting=false,revision=0;
async function place(cell,remove=false,kind=tool){
 if(editing||starting)return;
 const m=current(),[x,y]=cell;if(x<0||y<0||x>=m.width||y>=m.height)return;
 const same=p=>p[0]===x&&p[1]===y,hasO=objects.some(same),hasP=pedestrians.some(same);
 const o=objects.filter(p=>!same(p)),q=pedestrians.filter(p=>!same(p));
 if(!remove&&kind!=='remove'){if(kind==='object'&&!hasO)o.push([x,y]);if(kind==='ped'&&!hasP)q.push([x,y]);}
 editing=true;$('startBtn').disabled=true;
 try{const v=await api('/api/validate',{method:'POST',body:JSON.stringify({maze_id:m.id,objects:o,pedestrians:q})});if(!v.valid){toast(v.errors.join(' '));return}objects=o;pedestrians=q;renderEditor()}catch(e){toast(e.message)}finally{editing=false;$('startBtn').disabled=false}
}
function moveCursor(dx,dy){const m=current();cursor=[Math.max(0,Math.min(m.width-1,cursor[0]+dx)),Math.max(0,Math.min(m.height-1,cursor[1]-dy))];renderEditor()}
function cycleStrategy(delta){const all=['periodic','age','uncertainty'];const i=all.indexOf(strategy);document.querySelector(`[data-strategy="${all[(i+delta+all.length)%all.length]}"]`)?.click()}
function setMaze(n){if(editing||starting)return;revision++;mazeIndex=(n+catalog.length)%catalog.length;cursor=[Math.min(cursor[0],current().width-1),Math.min(cursor[1],current().height-1)];clearEdits()}
function pointerCell(e){
 const canvas=e.currentTarget,r=canvas.getBoundingClientRect(),d=dimensions(canvas,current());
 const scale=Math.min(r.width/canvas.width,r.height/canvas.height);
 const px=(e.clientX-r.left-(r.width-canvas.width*scale)/2)/scale;
 const py=(e.clientY-r.top-(r.height-canvas.height*scale)/2)/scale;
 return [Math.floor((px-d.x)/d.scale),current().height-1-Math.floor((py-d.y)/d.scale)];
}
$('editorCanvas').addEventListener('pointermove',e=>{const [x,y]=pointerCell(e);cursor=[Math.max(0,Math.min(current().width-1,x)),Math.max(0,Math.min(current().height-1,y))];renderEditor()});
$('editorCanvas').addEventListener('pointerdown',e=>{const [x,y]=pointerCell(e);if(x<0||y<0||x>=current().width||y>=current().height)return;cursor=[x,y];place(cursor,e.button===2)});
$('editorCanvas').addEventListener('contextmenu',e=>e.preventDefault());$('prevMaze').onclick=()=>setMaze(mazeIndex-1);$('nextMaze').onclick=()=>setMaze(mazeIndex+1);$('objectTool').onclick=()=>setTool('object');$('pedTool').onclick=()=>setTool('ped');$('removeTool').onclick=()=>setTool('remove');document.querySelectorAll('.strategy').forEach(b=>b.onclick=()=>{strategy=b.dataset.strategy;$('hero').dataset.pose=strategy;$('portraitStatus').hidden=true;$('heroImage').hidden=false;$('heroImage').src='/api/portrait/'+strategy+'?v=7';playHeroMotion(strategy);document.querySelectorAll('.strategy').forEach(x=>x.classList.toggle('active',x===b))});
function screen(name){document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));$(name).classList.add('active');if(name==='setupScreen')playHeroMotion(strategy)}
async function startChallenge(cfg=null){if(starting||editing)return;starting=true;try{const payload=cfg||{maze_id:current().id,objects,pedestrians,strategy,render_3d:$('render3d').checked};const v=await api('/api/challenge',{method:'POST',body:JSON.stringify(payload)});if(!v.ok)throw Error(v.error);lastConfig=payload;latestFrame=-1;$('liveMaze').textContent=`MAZE ${mazeIndex+1}`;$('liveStrategy').textContent=payload.strategy.toUpperCase();$('scene3d').hidden=true;$('truthCanvas').hidden=false;$('renderStatus').textContent='';screen('liveScreen');connectWS()}finally{starting=false}}
$('startBtn').onclick=()=>startChallenge().catch(e=>toast(e.message));function connectWS(){if(ws)ws.close();ws=new WebSocket(`ws://${location.host}/ws`);ws.onclose=()=>{if($('liveScreen').classList.contains('active'))setTimeout(connectWS,900)};ws.onmessage=e=>{const s=JSON.parse(e.data);if(s.status==='error'){$('liveStatus').textContent=s.error;return}if(s.status==='idle')return;if(s.frame_seq!==latestFrame){latestFrame=s.frame_seq;drawLive(s)}if(s.status==='finished'){lastResult=s.result;showResult(s.result)}}}
function drawLive(s){
 if(s.render_png){$('scene3d').src='data:image/png;base64,'+s.render_png;$('scene3d').hidden=false;$('truthCanvas').hidden=true}
 else{$('scene3d').hidden=true;$('truthCanvas').hidden=false}
 $('renderStatus').textContent=s.render_error?'3D unavailable · 2D fallback':'';
 $('stepValue').textContent=s.step??0;$('obsValue').textContent=s.observations??0;
 const m=current(),robot=s.position?{position:s.position,heading_yaw:s.heading_yaw||0}:null;
 const common={northUp:true,objects:s.objects||[],peds:s.people||[],robot,trajectory:s.trajectory||[]};
 drawMap($('truthCanvas'),m,common);
 drawMap($('memoryCanvas'),m,{...common,memory:s.memory||m.wall_rows.map(r=>r.split('').map(()=>-1)),observedObjects:s.observed_objects||[],observedPeople:s.observed_people||[]});
 $('liveStatus').textContent='';
}
function showResult(r){screen('resultScreen');const w=$('winner');w.textContent=r.winner;w.classList.toggle('human',r.winner==='HUMAN WINS');$('winnerCaption').textContent=r.winner==='AI WINS'?'The G1 reached the goal safely within 80 steps.':(r.success&&r.actual_unwanted_contacts>0?'The G1 reached the goal, but experienced actual unwanted contact.':'The G1 did not safely reach the goal within 80 steps.');const items=[['MAZE',`MAZE ${catalog.findIndex(m=>m.id===r.maze_id)+1}`],['STRATEGY',r.strategy.toUpperCase()],['GOAL',r.success?'REACHED':'NOT REACHED'],['STEPS',r.elapsed_steps],['OBSERVATIONS',r.observation_count],['DISTANCE',`${Number(r.travel_distance_m||0).toFixed(1)} m`],['ACTUAL CONTACTS',r.actual_unwanted_contacts],['BLOCKED ATTEMPTS',''+r.blocked_attempts_not_contacts]];$('resultSummary').innerHTML=items.map(x=>`<div><small>${x[0]}</small><b>${x[1]}</b></div>`).join('')}
async function backToEditor(keep){if(starting)return;starting=true;try{await api('/api/reset',{method:'POST'});if(ws){ws.onclose=null;ws.close()}screen('setupScreen');if(keep){renderEditor();await validate()}else clearEdits()}catch(e){toast(e.message)}finally{starting=false}}
$('newBtn').onclick=()=>backToEditor(true);
function pressed(pad,i){return !!pad.buttons[i]?.pressed||(pad.buttons[i]?.value||0)>.55}
const repeats={};let lastMove=0;
function gamepadLoop(){const gp=[...(navigator.getGamepads?.()||[])].find(Boolean);const padStatus=$('padStatus');padStatus.classList.toggle('connected',!!gp);padStatus.setAttribute('aria-label',gp?'Controller connected':'Controller disconnected');const now=performance.now(),cur=new Set();
if(gp){for(let i=0;i<gp.buttons.length;i++)if(pressed(gp,i))cur.add(i);const edge=i=>cur.has(i)&&!gamepadPrev.has(i);
const repeat=(i,fn)=>{if(!cur.has(i)){delete repeats[i];return}if(edge(i)||now>=(repeats[i]??0)){fn();repeats[i]=now+(edge(i)?350:140)}};
if($('setupScreen').classList.contains('active')){let dx=Math.abs(gp.axes[0]||0)>.24?Math.sign(gp.axes[0]):0,dy=Math.abs(gp.axes[1]||0)>.24?Math.sign(gp.axes[1]):0;if((dx||dy)&&now-lastMove>125){moveCursor(dx,dy);lastMove=now}repeat(6,()=>setMaze(mazeIndex-1));repeat(7,()=>setMaze(mazeIndex+1));if(edge(14)||edge(12))cycleStrategy(-1);if(edge(15)||edge(13))cycleStrategy(1);if(edge(2))place([...cursor],false,'object');else if(edge(3))place([...cursor],false,'ped');else if(edge(1))place([...cursor],true);else if(edge(0))$('startBtn').click()}
else if($('resultScreen').classList.contains('active')){if(edge(0))$('newBtn').click()}
}else{for(const k of Object.keys(repeats))delete repeats[k]}gamepadPrev=cur;requestAnimationFrame(gamepadLoop)}
window.addEventListener('keydown',e=>{if(!$('setupScreen').classList.contains('active'))return;const k=e.key.toLowerCase();if(k==='arrowleft')moveCursor(-1,0);else if(k==='arrowright')moveCursor(1,0);else if(k==='arrowup')moveCursor(0,-1);else if(k==='arrowdown')moveCursor(0,1);else if(k==='[')setMaze(mazeIndex-1);else if(k===']')setMaze(mazeIndex+1);else if(k==='x')place([...cursor],false,'object');else if(k==='y')place([...cursor],false,'ped');else if(k==='b'||k==='backspace')place(cursor,true);else if(k==='enter')$('startBtn').click();else if(k===' '){e.preventDefault();startChallenge().catch(e=>toast(e.message))}else if('123'.includes(k)){document.querySelector(`[data-strategy="${['','periodic','age','uncertainty'][+k]}"]`)?.click()}});
(async()=>{try{const d=await api('/api/catalog');catalog=d.mazes;$('objectCount').dataset.max=d.max_static_objects;$('pedCount').dataset.max=d.max_pedestrians;renderEditor();validate();gamepadLoop();playHeroMotion(strategy)}catch(e){toast(e.message);console.error(e)}})();

$('heroImage').onerror=async()=>{const img=$('heroImage'),url=img.src;img.hidden=true;const status=$('portraitStatus');status.hidden=false;status.textContent='G1 portrait unavailable';try{const response=await fetch(url);if(!response.ok){const data=await response.json();if(img.src===url){status.textContent='G1 portrait unavailable: '+String(data.error||response.status).split('\n').filter(Boolean).pop();console.error('G1 portrait:',data.error)}}}catch(error){console.error(error)}};

const motionCache=new Map();let motionToken=0;
function motionAsset(name){
 if(!motionCache.has(name)){
  const promise=new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Motion image unavailable'));im.src='/api/portrait/'+name+'?motion=true&v=7'});
  motionCache.set(name,promise);promise.catch(()=>motionCache.delete(name));
 }
 return motionCache.get(name);
}
async function playHeroMotion(name){
 const token=++motionToken,canvas=$('heroMotion'),img=$('heroImage');
 canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
 canvas.hidden=true;img.classList.remove('motion-playing');
 try{
  const atlas=await motionAsset(name);
  if(token!==motionToken||!$('setupScreen').classList.contains('active'))return;
  const ctx=canvas.getContext('2d'),start=performance.now();
  canvas.hidden=false;img.classList.add('motion-playing');
  function tick(now){
   if(token!==motionToken)return;
   const elapsed=now-start;
   if(elapsed>=3000||!$('setupScreen').classList.contains('active')){
    ctx.clearRect(0,0,canvas.width,canvas.height);canvas.hidden=true;img.classList.remove('motion-playing');return;
   }
   const frame=Math.min(59,Math.floor(elapsed*20/1000));
   ctx.clearRect(0,0,canvas.width,canvas.height);
   ctx.drawImage(atlas,(frame%6)*360,Math.floor(frame/6)*480,360,480,0,0,360,480);
   requestAnimationFrame(tick);
  }
  tick(start);
 }catch(error){console.warn(error)}
}
// Prepare the clips sequentially; cached images require no live MuJoCo work.
(async()=>{for(const name of ['periodic','age','uncertainty']){
 try{await motionAsset(name)}catch(error){console.warn(error)}
}})();
