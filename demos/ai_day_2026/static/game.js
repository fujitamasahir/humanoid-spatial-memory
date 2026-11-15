'use strict';
const $=id=>document.getElementById(id);let catalog=[],mazeIndex=0,objects=[],pedestrians=[],strategy='periodic',tool='object',cursor=[1,1],cellGeom=null,latestFrame=-1,lastResult=null,lastConfig=null,gamepadPrev=new Set(),lastPadAction=0,ws;
let difficulty='easy',difficultyRules={},pendingDifficulty='easy',settingsOpen=false;
const LEVELS=['easy','medium','hard'];
let liveState=null,pausedDraft=null,pauseBusy=false,pauseTool='object',pauseCursor=[1,1];
let skipping=false,reviewSteps=[],reviewCursor=0,reviewRequest=0,reviewOpening=false;
let reviewHold={dir:0,since:0,next:0};
const rules=()=>difficultyRules[difficulty];
const colors={wall:'#263647',free:'#101a26',unknown:'#5f6978',memoryFree:'#174247',memoryWall:'#60413a',object:'#f19a43',ped:'#f26970',cyan:'#49e0eb',gold:'#ffca63',robot:'#64b4ff'};
async function api(url,options={}){const r=await fetch(url,{headers:{'Content-Type':'application/json'},...options});let d=await r.json();if(!r.ok)throw Error(d.detail||d.error||`HTTP ${r.status}`);return d}
function toast(s){$('toast').textContent=s;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),2300)}
function current(){return catalog[mazeIndex]}
function setTool(t){tool=t;for(const [id,v] of [['objectTool','object'],['pedTool','ped']])$(id).classList.toggle('active',t===v)}
function dimensions(canvas,maze){const pad=30,scale=Math.min((canvas.width-pad*2)/maze.width,(canvas.height-pad*2)/maze.height);const w=scale*maze.width,h=scale*maze.height;return {x:(canvas.width-w)/2,y:(canvas.height-h)/2,scale,w,h}}
function drawMap(canvas,maze,{memory=null,objects:obs=[],peds=[],robot=null,trajectory=[],cursorCell=null,editor=false,northUp=false,observedObjects=[],observedPeople=[]}={}){const ctx=canvas.getContext('2d',{alpha:false});ctx.fillStyle='#0b111a';ctx.fillRect(0,0,canvas.width,canvas.height);const d=dimensions(canvas,maze);cellGeom=d;const displayY=y=>northUp?maze.height-1-y:y;for(let y=0;y<maze.height;y++)for(let x=0;x<maze.width;x++){const bit=maze.wall_rows[y][x],v=memory?memory[y][x]:null;const wallColor=({R:'#355c88',BP:'#327d70',M:'#76529b'}[maze.mechanism]||colors.wall);ctx.fillStyle=memory?(v<0?(bit==='1'?wallColor:colors.free):v===1?wallColor:colors.memoryFree):(bit==='1'?wallColor:colors.free);ctx.globalAlpha=memory&&v<0?.23:1;ctx.fillRect(d.x+x*d.scale,d.y+displayY(y)*d.scale,d.scale-.7,d.scale-.7);ctx.globalAlpha=1;if((!memory||v===1)&&bit==='1'){const X=d.x+x*d.scale,Y=d.y+displayY(y)*d.scale,z=d.scale;ctx.fillStyle='#ffffff25';ctx.fillRect(X,Y,z-.7,z*.16);ctx.fillStyle='#00000055';ctx.fillRect(X,Y+z*.72,z-.7,z*.28);ctx.fillRect(X+z*.78,Y,z*.22,z*.72)}if(!memory&&bit==='0'){ctx.fillStyle='#ffffff08';ctx.fillRect(d.x+x*d.scale+1,d.y+displayY(y)*d.scale+1,d.scale-2,d.scale-2)}}
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
   ctx.fillStyle=({R:'#659fe0',BP:'#56c6aa',M:'#a58be7'}[m.mechanism]||'#94a6b8');
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
function renderEditor(){const m=current();drawMap($('editorCanvas'),m,{northUp:true,objects,peds:pedestrians,editor:true,cursorCell:cursor});$('mazeIdentity').textContent=`MAZE ${String(mazeIndex+1).padStart(2,'0')} / ${catalog.length}`;$('mazeType').textContent='TYPE '+m.mechanism;$('mazeType').dataset.type=m.mechanism;updateMazeStrip();for(const [id,used,icon] of [['objectCount',objects.length,'◆'],['pedCount',pedestrians.length,'♟']]){const el=$(id);el.replaceChildren(...Array.from({length:Number(el.dataset.max)},(_,i)=>{const s=document.createElement('i');s.className=i<used?'spent':'';s.innerHTML=inventoryIcon(id==='objectCount');return s}))}}
async function validate(){const rev=revision;const v=await api('/api/validate',{method:'POST',body:JSON.stringify({maze_id:current().id,objects,pedestrians,difficulty})});if(rev!==revision||editing)return v;const el=$('validation');el.textContent=v.valid?'':v.errors.join(' ');el.hidden=v.valid;el.classList.toggle('error',!v.valid);$('startBtn').disabled=!v.valid;return v}
function clearEdits(){objects=[];pedestrians=[];validate().catch(e=>toast(e.message));renderEditor()}
let editing=false,starting=false,revision=0;
async function place(cell,remove=false,kind=tool){
 if(editing||starting||settingsOpen)return;
 const m=current(),[x,y]=cell;if(x<0||y<0||x>=m.width||y>=m.height)return;
 const same=p=>p[0]===x&&p[1]===y,hasO=objects.some(same),hasP=pedestrians.some(same);
 const o=objects.filter(p=>!same(p)),q=pedestrians.filter(p=>!same(p));
 if(!remove&&kind!=='remove'){if(kind==='object'&&!hasO)o.push([x,y]);if(kind==='ped'&&!hasP)q.push([x,y]);}
 editing=true;$('startBtn').disabled=true;
 try{const v=await api('/api/validate',{method:'POST',body:JSON.stringify({maze_id:m.id,objects:o,pedestrians:q,difficulty})});if(!v.valid){toast(v.errors.join(' '));return}objects=o;pedestrians=q;renderEditor()}catch(e){toast(e.message)}finally{editing=false;$('startBtn').disabled=false}
}
function moveCursor(dx,dy){const m=current();cursor=[Math.max(0,Math.min(m.width-1,cursor[0]+dx)),Math.max(0,Math.min(m.height-1,cursor[1]-dy))];renderEditor()}
function cycleStrategy(delta){const i=HERO_NAMES.indexOf(strategy);selectHero(HERO_NAMES[(i+delta+3)%3],delta)}
function setMaze(n){if(editing||starting||settingsOpen)return;revision++;mazeIndex=(n+catalog.length)%catalog.length;cursor=[Math.min(cursor[0],current().width-1),Math.min(cursor[1],current().height-1)];clearEdits()}
function pointerCell(e){
 const canvas=e.currentTarget,r=canvas.getBoundingClientRect(),d=dimensions(canvas,current());
 const scale=Math.min(r.width/canvas.width,r.height/canvas.height);
 const px=(e.clientX-r.left-(r.width-canvas.width*scale)/2)/scale;
 const py=(e.clientY-r.top-(r.height-canvas.height*scale)/2)/scale;
 return [Math.floor((px-d.x)/d.scale),current().height-1-Math.floor((py-d.y)/d.scale)];
}
$('editorCanvas').addEventListener('pointermove',e=>{const [x,y]=pointerCell(e);cursor=[Math.max(0,Math.min(current().width-1,x)),Math.max(0,Math.min(current().height-1,y))];renderEditor()});
$('editorCanvas').addEventListener('pointerdown',e=>{const [x,y]=pointerCell(e);if(x<0||y<0||x>=current().width||y>=current().height)return;cursor=[x,y];place(cursor,e.button===2)});
$('editorCanvas').addEventListener('contextmenu',e=>e.preventDefault());$('prevMaze').onclick=()=>setMaze(mazeIndex-1);$('nextMaze').onclick=()=>setMaze(mazeIndex+1);$('objectTool').onclick=()=>setTool('object');$('pedTool').onclick=()=>setTool('ped');document.querySelectorAll('.strategy').forEach(b=>b.onclick=()=>selectHero(b.dataset.strategy));
function screen(name){stopResultEffects();$('settingsBtn').hidden=name!=='setupScreen';document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));$(name).classList.add('active');if(name==='setupScreen'){positionHeroRing(heroAngle);playHeroMotion(strategy)}else {++heroSpin;heroTarget=HERO_NAMES.indexOf(strategy);positionHeroRing(heroTarget);stopHeroMotion()}}
async function startChallenge(cfg=null){if(starting||editing||settingsOpen||$('startBtn').disabled)return;starting=true;try{const payload=cfg||{maze_id:current().id,objects,pedestrians,strategy,difficulty,render_3d:$('render3d').checked};const v=await api('/api/challenge',{method:'POST',body:JSON.stringify(payload)});if(!v.ok)throw Error(v.error);lastConfig=payload;latestFrame=-1;skipping=false;liveState=null;pausedDraft=null;pauseBusy=false;syncPauseControls();reviewSteps=[];reviewRequest++;$('skipBtn').disabled=false;$('skipBtn').innerHTML='<kbd class="a">A</kbd> SKIP TO RESULTS';$('liveContact').hidden=true;$('liveContact').textContent='';$('stepValue').textContent='0';$('obsValue').textContent='0';$('liveMaze').textContent=`MAZE ${mazeIndex+1}`;$('liveStrategy').textContent=payload.strategy.toUpperCase();$('liveDifficulty').textContent=(payload.difficulty||difficulty).toUpperCase();$('stepLimit').textContent='/ '+rules().step_limit;$('obsLimit').textContent='/ '+rules().max_observations;$('scene3d').hidden=true;$('truthCanvas').hidden=false;$('renderStatus').textContent='';screen('liveScreen');connectWS()}finally{starting=false}}
$('startBtn').onclick=()=>startChallenge().catch(e=>toast(e.message));function connectWS(){if(ws)ws.close();ws=new WebSocket(`ws://${location.host}/ws`);ws.onclose=()=>{if($('liveScreen').classList.contains('active'))setTimeout(connectWS,900)};ws.onmessage=e=>{const s=JSON.parse(e.data);if(s.status==='error'){$('liveStatus').textContent=s.error;return}if(s.status==='idle')return;const changed=s.frame_seq!==latestFrame||s.status!==liveState?.status;liveState=s;if(changed){latestFrame=s.frame_seq;if(!skipping)drawLive(s)}if(s.status==='finished'&&$('liveScreen').classList.contains('active')){lastResult=s.result;showResult(s.result,s)}}}
async function skipChallenge(){
 if(skipping||pauseBusy||liveState?.status!=='running'||!$('liveScreen').classList.contains('active'))return;
 skipping=true;$('skipBtn').disabled=true;$('skipBtn').textContent='FINISHING CHALLENGE…';
 try{await api('/api/skip',{method:'POST'})}
 catch(error){skipping=false;$('skipBtn').disabled=false;$('skipBtn').innerHTML='<kbd class="a">A</kbd> SKIP TO RESULTS';toast(error.message)}
}
$('skipBtn').onclick=skipChallenge;
const sameCell=(a,b)=>!!a&&!!b&&a[0]===b[0]&&a[1]===b[1];
const paused=()=>liveState?.status==='paused'&&!!pausedDraft;
function setPauseTool(kind){pauseTool=kind;$('pauseObject').classList.toggle('active',kind==='object');$('pausePed').classList.toggle('active',kind==='ped')}
function syncPauseControls(){
 const status=liveState?.status||'running',isPaused=status==='paused',pending=pauseBusy||status==='pausing'||status==='resuming';
 $('pauseBtn').innerHTML='<kbd class="b">B</kbd> '+(status==='pausing'?'PAUSING…':status==='resuming'?'RESUMING…':isPaused?'RESUME':'PAUSE');
 $('pauseBtn').disabled=pending||skipping||!['running','paused'].includes(status);
 $('skipBtn').disabled=pending||isPaused||skipping;
 $('pauseTools').hidden=!isPaused;
 $('livePanelTitle').textContent=isPaused?'TIME STOPPED · EDIT ENVIRONMENT':'HUMANOID IN MOTION';
 $('liveScreen').classList.toggle('paused',isPaused);
 if(isPaused&&pausedDraft){const rule=difficultyRules[liveState.difficulty];$('pauseObjectCount').textContent=pausedDraft.objects.length+' / '+rule.max_static_objects;$('pausePedCount').textContent=pausedDraft.pedestrians.length+' / '+rule.max_pedestrians;$('pausePed').disabled=rule.max_pedestrians===0;}
}
function drawPauseEditor(){if(!paused())return;const s=liveState;drawMap($('truthCanvas'),current(),{northUp:true,objects:pausedDraft.objects,peds:pausedDraft.pedestrians,robot:{position:s.position,heading_yaw:s.heading_yaw||0},trajectory:s.trajectory||[],editor:true,cursorCell:pauseCursor});syncPauseControls()}
function movePauseCursor(dx,dy){if(!paused()||pauseBusy)return;const m=current();pauseCursor=[Math.max(0,Math.min(m.width-1,pauseCursor[0]+dx)),Math.max(0,Math.min(m.height-1,pauseCursor[1]-dy))];drawPauseEditor()}
async function editPaused(cell,kind=pauseTool,removeOnly=false){
 if(!paused()||pauseBusy)return;
 const m=current(),[x,y]=cell,rule=difficultyRules[liveState.difficulty],items=kind==='object'?pausedDraft.objects:pausedDraft.pedestrians,other=kind==='object'?pausedDraft.pedestrians:pausedDraft.objects,cap=kind==='object'?rule.max_static_objects:rule.max_pedestrians;
 const index=items.findIndex(p=>sameCell(p,cell));
 if(index>=0){items.splice(index,1);drawPauseEditor();return}
 if(removeOnly)return;
 if(x<0||y<0||x>=m.width||y>=m.height||m.wall_rows[y][x]!=='0'||sameCell(cell,m.start)||sameCell(cell,m.goal)||sameCell(cell,liveState.position)){toast('Choose an open cell away from Start, Goal and the humanoid.');return}
 if(other.some(p=>sameCell(p,cell))){toast('Remove the other hazard first.');return}
 if(items.length>=cap){toast('Placement limit reached. Remove an existing '+(kind==='object'?'object':'pedestrian')+' first.');return}
 const draft=pausedDraft;
 const candidate={step:draft.step,objects:draft.objects.map(p=>[...p]),pedestrians:draft.pedestrians.map(p=>[...p])};
 (kind==='object'?candidate.objects:candidate.pedestrians).push([...cell]);
 pauseBusy=true;syncPauseControls();
 try{
  const verdict=await api('/api/validate-paused',{method:'POST',body:JSON.stringify(candidate)});
  if(!paused()||pausedDraft!==draft)return;
  if(!verdict.valid){toast(verdict.errors.join(' '));return}
  pausedDraft=candidate;drawPauseEditor();
 }catch(error){toast(error.message)}finally{pauseBusy=false;syncPauseControls()}
}
async function togglePause(){
 if(pauseBusy||skipping||!$('liveScreen').classList.contains('active')||!['running','paused'].includes(liveState?.status))return;
 const wasPaused=paused();pauseBusy=true;syncPauseControls();
 try{
  const options={method:'POST'};
  if(wasPaused)options.body=JSON.stringify({step:pausedDraft.step,objects:pausedDraft.objects,pedestrians:pausedDraft.pedestrians});
  await api(wasPaused?'/api/resume':'/api/pause',options);
  // WebSocket owns authoritative paused state; do not discard the draft on validation failure.
 }catch(error){toast(error.message)}finally{pauseBusy=false;syncPauseControls()}
}
$('pauseBtn').onclick=togglePause;$('pauseObject').onclick=()=>setPauseTool('object');$('pausePed').onclick=()=>setPauseTool('ped');
$('truthCanvas').addEventListener('pointermove',e=>{if(!paused()||pauseBusy)return;const [x,y]=pointerCell(e),m=current();if(x>=0&&y>=0&&x<m.width&&y<m.height){pauseCursor=[x,y];drawPauseEditor()}});
$('truthCanvas').addEventListener('pointerdown',e=>{if(!paused()||pauseBusy)return;const [x,y]=pointerCell(e),m=current();if(x<0||y<0||x>=m.width||y>=m.height)return;pauseCursor=[x,y];if(e.button===2){const kind=pausedDraft.objects.some(p=>sameCell(p,pauseCursor))?'object':'ped';editPaused(pauseCursor,kind,true)}else if(e.button===0)editPaused(pauseCursor)});
$('truthCanvas').addEventListener('contextmenu',e=>{if(paused())e.preventDefault()});
function drawMemory(canvas,m,s){
 const robot=s.position?{position:s.position,heading_yaw:s.heading_yaw||0}:null;
 drawMap(canvas,m,{northUp:true,objects:s.objects||[],peds:s.people||[],robot,trajectory:s.trajectory||[],memory:s.memory||m.wall_rows.map(r=>r.split('').map(()=>-1)),observedObjects:s.observed_objects||[],observedPeople:s.observed_people||[]});
}
function drawLive(s){
 if(s.status==='paused'&&(!pausedDraft||pausedDraft.step!==s.step)){pausedDraft={step:s.step,objects:(s.objects||[]).map(p=>[...p]),pedestrians:(s.people||[]).map(p=>[...p])};pauseCursor=[...(s.position||[1,1])];setPauseTool('object')}
 if(s.status==='running')pausedDraft=null;
 syncPauseControls();
 if(s.status==='paused'){$('scene3d').hidden=true;$('truthCanvas').hidden=false}
 else if(s.render_png){$('scene3d').src='data:image/png;base64,'+s.render_png;$('scene3d').hidden=false;$('truthCanvas').hidden=true}
 else{$('scene3d').hidden=true;$('truthCanvas').hidden=false}
 $('renderStatus').textContent=s.render_error?'3D unavailable · 2D fallback':'';
 $('stepValue').textContent=s.step??0;$('obsValue').textContent=s.observations??0;
 const m=current(),robot=s.position?{position:s.position,heading_yaw:s.heading_yaw||0}:null;
 const common={northUp:true,objects:s.objects||[],peds:s.people||[],robot,trajectory:s.trajectory||[]};
 if(s.status==='paused')drawPauseEditor();else drawMap($('truthCanvas'),m,common);
 drawMemory($('memoryCanvas'),m,s);
 $('liveStatus').textContent=s.status==='pausing'?'Stopping at the next completed step…':s.status==='resuming'?'Resuming simulation…':'';
 const hits=s.contact_events||[];const last=hits[hits.length-1];
 $('liveContact').hidden=!last;if(last)$('liveContact').textContent=contactMessage(last);
}
function contactMessage(event){
 const labels={g1_pedestrian_contact_pairs:'PEDESTRIAN COLLISION',g1_wall_contact_pairs:'WALL COLLISION',g1_persistent_obstacle_contact_pairs:'OBJECT COLLISION',g1_unwanted_floor_contact_pairs:'UNWANTED FLOOR CONTACT',g1_self_contact_pairs:'SELF COLLISION'};
 return 'STEP '+event.step+' · '+Object.keys(labels).filter(k=>event.contacts[k]>0).map(k=>labels[k]).join(' / ');
}
function showResult(r,finalState){
 skipping=false;
 screen('resultScreen');const w=$('winner'),human=r.winner==='HUMAN WINS',limit=r.step_limit??rules().step_limit;
 w.textContent=r.winner;w.classList.toggle('human',human);
 const hit=(r.contact_events||[]).find(e=>e.contacts.g1_pedestrian_contact_pairs>0)||(r.contact_events||[])[0];
 const caption=$('winnerCaption');
 caption.classList.toggle('contact-alert',!!hit);
 caption.classList.toggle('result-contact-alert',!!hit);
 caption.hidden=!hit;
 caption.textContent=hit?contactMessage(hit):'';
 const items=[['MAZE',String(catalog.findIndex(m=>m.id===r.maze_id)+1)],['STRATEGY',r.strategy.toUpperCase()],['DIFFICULTY',(r.difficulty||difficulty).toUpperCase()],['STEPS',r.elapsed_steps+' / '+limit],['OBSERVATIONS',r.observation_count+' / '+(r.max_observations??rules().max_observations)]];
 $('resultSummary').replaceChildren(...items.map(([key,value])=>{const box=document.createElement('div'),label=document.createElement('small'),num=document.createElement('b');box.dataset.stat=key.toLowerCase();label.textContent=key;num.textContent=value;box.append(label,num);return box}));
 const m=catalog.find(x=>x.id===r.maze_id)||current();drawMemory($('finalMemoryCanvas'),m,finalState);
 showResultReaction(r.strategy,human);
}
async function backToEditor(keep){if(starting)return;starting=true;try{await api('/api/reset',{method:'POST'});if(ws){ws.onclose=null;ws.close()}screen('setupScreen');if(keep){renderEditor();await validate()}else clearEdits()}catch(e){toast(e.message)}finally{starting=false}}
$('newBtn').onclick=()=>backToEditor(true);
$('experimentReviewBtn').onclick=()=>{if(!settingsOpen&&!starting&&!editing&&$('setupScreen').classList.contains('active'))location.href='/h2-review.html'};
let fullscreenPending=false;
function fullscreenElement(){return document.fullscreenElement||document.webkitFullscreenElement||null}
function syncFullscreen(){
 const active=!!fullscreenElement(),b=$('fullscreenBtn');
 b.setAttribute('aria-pressed',String(active));
 b.setAttribute('aria-label',active?'Exit fullscreen':'Enter fullscreen');
 b.title=(active?'Exit fullscreen':'Fullscreen')+' (Xbox View button)';
}
async function toggleFullscreen(){
 if(fullscreenPending)return;
 fullscreenPending=true;
 try{
  if(fullscreenElement()){
   const exit=document.exitFullscreen||document.webkitExitFullscreen;
   if(!exit)throw Error('Fullscreen exit unavailable');
   await exit.call(document);
  }else{
   const root=document.documentElement,enter=root.requestFullscreen||root.webkitRequestFullscreen;
   if(!enter)throw Error('Fullscreen unavailable');
   await enter.call(root);
  }
 }catch(error){toast('Fullscreen was blocked. Click the fullscreen icon in the top right.')}
 finally{fullscreenPending=false;syncFullscreen()}
}
$('fullscreenBtn').addEventListener('click',toggleFullscreen);
document.addEventListener('fullscreenchange',syncFullscreen);
document.addEventListener('webkitfullscreenchange',syncFullscreen);
syncFullscreen();
function pressed(pad,i){return !!pad.buttons[i]?.pressed||(pad.buttons[i]?.value||0)>.55}
const repeats={};let lastMove=0,heroStickDir=0,padReady=false;
function stickDirection(x,prev){return Math.abs(x)<.24?0:Math.abs(x)>.38?Math.sign(x):prev}
let difficultyStick={dir:0,next:0,armed:false};
function difficultyStickStep(state,x,y,now){
 const axis=Math.abs(y)>=Math.abs(x)?y:x;
 if(Math.max(Math.abs(x),Math.abs(y))<.24)return {state:{dir:0,next:0,armed:true},delta:0};
 if(!state.armed||Math.abs(axis)<.38)return {state,delta:0};
 const dir=Math.sign(axis);
 if(dir!==state.dir)return {state:{dir,next:now+350,armed:true},delta:dir};
 if(now>=state.next)return {state:{dir,next:now+180,armed:true},delta:dir};
 return {state,delta:0};
}
function resetDifficultyStick(){difficultyStick={dir:0,next:0,armed:false}}
function gamepadLoop(){const gp=[...(navigator.getGamepads?.()||[])].find(Boolean);const padStatus=$('padStatus');padStatus.classList.toggle('connected',!!gp);padStatus.setAttribute('aria-label',gp?'Controller connected':'Controller disconnected');const now=performance.now(),cur=new Set();
if(gp){for(let i=0;i<gp.buttons.length;i++)if(pressed(gp,i))cur.add(i);if(!padReady){gamepadPrev=cur;padReady=true}const edge=i=>cur.has(i)&&!gamepadPrev.has(i);
if(edge(8))toggleFullscreen();
const repeat=(i,fn)=>{if(!cur.has(i)){delete repeats[i];return}if(edge(i)||now>=(repeats[i]??0)){fn();repeats[i]=now+(edge(i)?350:140)}};
if(settingsOpen){const s=difficultyStickStep(difficultyStick,gp.axes[0]||0,gp.axes[1]||0,now);difficultyStick=s.state;if(edge(0))applyDifficulty();else if(edge(1)||edge(9))closeSettings();else if(edge(12)||edge(14))moveDifficulty(-1);else if(edge(13)||edge(15))moveDifficulty(1);else if(s.delta&&!cur.has(12)&&!cur.has(13)&&!cur.has(14)&&!cur.has(15))moveDifficulty(s.delta)}
else if($('setupScreen').classList.contains('active')){if(edge(9)){openSettings()}else {let dx=Math.abs(gp.axes[0]||0)>.24?Math.sign(gp.axes[0]):0,dy=Math.abs(gp.axes[1]||0)>.24?Math.sign(gp.axes[1]):0;if((dx||dy)&&now-lastMove>125){moveCursor(dx,dy);lastMove=now}repeat(14,()=>setMaze(mazeIndex-1));repeat(15,()=>setMaze(mazeIndex+1));if(edge(12))setMaze(mazeIndex-1);if(edge(13))setMaze(mazeIndex+1);const dir=stickDirection(gp.axes[2]||0,heroStickDir);if(dir&&dir!==heroStickDir)cycleStrategy(dir);heroStickDir=dir;if(edge(6))changeDifficulty(-1);else if(edge(7))changeDifficulty(1);if(edge(2))place([...cursor],false,'object');else if(edge(3))place([...cursor],false,'ped');else if(edge(1))$('experimentReviewBtn').click();else if(edge(0))$('startBtn').click()}}
else if($('liveScreen').classList.contains('active')){if(edge(1))togglePause();else if(paused()&&!pauseBusy){const dx=Math.abs(gp.axes[0]||0)>.24?Math.sign(gp.axes[0]):(cur.has(15)?1:cur.has(14)?-1:0),dy=Math.abs(gp.axes[1]||0)>.24?Math.sign(gp.axes[1]):(cur.has(13)?1:cur.has(12)?-1:0);if((dx||dy)&&now-lastMove>125){movePauseCursor(dx,dy);lastMove=now}if(edge(2)){setPauseTool('object');editPaused([...pauseCursor],'object')}else if(edge(3)){setPauseTool('ped');editPaused([...pauseCursor],'ped')}}else if(edge(0))skipChallenge()}
else if($('resultScreen').classList.contains('active')){if(edge(0))$('newBtn').click();else if(edge(1))openReview()}
else if($('reviewScreen').classList.contains('active')){if(edge(1))closeReview();else if(edge(6)){resetReviewHold();renderReview(0)}else if(edge(7)){resetReviewHold();renderReview(reviewSteps.length-1)}else updateReviewSeek(gp,cur,now)}
}else{padReady=false;for(const k of Object.keys(repeats))delete repeats[k];resetReviewHold();resetDifficultyStick()}if(!$('reviewScreen').classList.contains('active'))resetReviewHold();if(!gp||settingsOpen||!$('setupScreen').classList.contains('active')){heroStickDir=0;delete repeats[14];delete repeats[15]}gamepadPrev=cur;requestAnimationFrame(gamepadLoop)}
window.addEventListener('keydown',e=>{const k=e.key.toLowerCase();if($('liveScreen').classList.contains('active')){if(['b','x','y','arrowleft','arrowright','arrowup','arrowdown','enter','a'].includes(k))e.preventDefault();if(k==='b'&&!e.repeat)togglePause();else if(paused()&&!pauseBusy){if(k==='arrowleft')movePauseCursor(-1,0);else if(k==='arrowright')movePauseCursor(1,0);else if(k==='arrowup')movePauseCursor(0,-1);else if(k==='arrowdown')movePauseCursor(0,1);else if(k==='x'&&!e.repeat){setPauseTool('object');editPaused([...pauseCursor],'object')}else if(k==='y'&&!e.repeat){setPauseTool('ped');editPaused([...pauseCursor],'ped')}}else if((k==='enter'||k==='a')&&!e.repeat)skipChallenge();return}if($('resultScreen').classList.contains('active')){if(k==='b'){e.preventDefault();if(!e.repeat)openReview()}else if(k==='enter'||k==='a'){e.preventDefault();if(!e.repeat)$('newBtn').click()}return}if($('reviewScreen').classList.contains('active')){if(k==='arrowleft'||k==='arrowright'){e.preventDefault();moveReview(k==='arrowleft'?-1:1)}else if(k==='escape'||k==='b'){e.preventDefault();if(!e.repeat)closeReview()}return}if(!$('setupScreen').classList.contains('active'))return;if(settingsOpen){if(['arrowup','arrowleft','arrowdown','arrowright','enter','escape','b','m'].includes(k)){e.preventDefault();if(k==='arrowup'||k==='arrowleft')moveDifficulty(-1);else if(k==='arrowdown'||k==='arrowright')moveDifficulty(1);else if(k==='enter')applyDifficulty();else closeSettings()}return}if(k==='m'||k==='escape'){e.preventDefault();openSettings();return}if(k==='arrowleft')moveCursor(-1,0);else if(k==='arrowright')moveCursor(1,0);else if(k==='arrowup')moveCursor(0,-1);else if(k==='arrowdown')moveCursor(0,1);else if(k==='[')setMaze(mazeIndex-1);else if(k===']')setMaze(mazeIndex+1);else if(k==='x')place([...cursor],false,'object');else if(k==='y')place([...cursor],false,'ped');else if(k==='b'){e.preventDefault();if(!e.repeat)$('experimentReviewBtn').click()}else if(k==='backspace')place(cursor,true);else if(k==='enter')$('startBtn').click();else if(k===' '){e.preventDefault();startChallenge().catch(e=>toast(e.message))}else if('123'.includes(k)){document.querySelector(`[data-strategy="${['','periodic','age','uncertainty'][+k]}"]`)?.click()}});
(async()=>{try{const d=await api('/api/catalog');catalog=d.mazes;difficultyRules=d.difficulties;syncDifficulty();renderEditor();validate();gamepadLoop();playHeroMotion(strategy)}catch(e){toast(e.message);console.error(e)}})();

const motionCache=new Map();let motionToken=0;
function motionAsset(name,reaction=''){
 const key=name+'|'+reaction;
 if(!motionCache.has(key)){
  const promise=new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Motion image unavailable'));im.src='/api/portrait/'+name+'?motion=true'+(reaction?'&reaction='+encodeURIComponent(reaction):'')+'&v=14'});
  motionCache.set(key,promise);promise.catch(()=>motionCache.delete(key));
 }
 return motionCache.get(key);
}
const HERO_NAMES=['periodic','age','uncertainty'];
const heroCards=Array.from(document.querySelectorAll('.hero-card'));
const strategyCards=HERO_NAMES.map(name=>document.querySelector('.strategy[data-strategy="'+name+'"]'));
let heroAngle=0,heroTarget=0,heroSpin=0;
function positionHeroRing(angle){
 heroAngle=angle;
 heroCards.forEach((card,i)=>{
  const theta=(i-angle)*2*Math.PI/3,depth=(Math.cos(theta)+1)/2;
  card.style.left=(50+Math.sin(theta)*31)+'%';
  card.style.top=(50-(1-depth)*8)+'%';
  card.style.transform='translate(-50%,-50%) scale('+(0.57+depth*.43)+')';
  card.style.opacity=String(.34+depth*.66);
  card.style.zIndex=String(1+Math.round(depth*100));
  const label=strategyCards[i];
  label.style.left=card.style.left;
  label.style.opacity=String(.34+depth*.66);
  label.style.zIndex=card.style.zIndex;
  label.style.transform='translateX(-50%) scale('+(0.82+depth*.18)+')';
  label.style.setProperty('--depth',depth);
  label.setAttribute('aria-pressed',String(card.dataset.character===strategy));
 });
}
function stopHeroMotion(){
 ++motionToken;
 const canvas=$('heroMotion');
 canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
 canvas.hidden=true;
 heroCards.forEach(card=>card.classList.remove('motion-playing'));
}
function selectHero(name,direction=0){
 if(!HERO_NAMES.includes(name)||!$('setupScreen').classList.contains('active')||settingsOpen)return;
 if(name===strategy&&!direction){playHeroMotion(name);return}
 stopHeroMotion();
 const previous=HERO_NAMES.indexOf(strategy),next=HERO_NAMES.indexOf(name);
 const delta=direction||((next-previous+3)%3===1?1:-1);
 strategy=name;heroTarget+=delta;$('hero').dataset.pose=name;$('portraitStatus').hidden=true;
 document.querySelectorAll('.strategy').forEach(b=>b.classList.toggle('active',b.dataset.strategy===name));
 const token=++heroSpin,from=heroAngle,to=heroTarget,start=performance.now();
 function turn(now){
  if(token!==heroSpin)return;
  const t=Math.min(1,(now-start)/480),ease=t*t*(3-2*t);
  positionHeroRing(from+(to-from)*ease);
  if(t<1)requestAnimationFrame(turn);
  else {heroTarget=HERO_NAMES.indexOf(strategy);positionHeroRing(heroTarget);if($('setupScreen').classList.contains('active'))playHeroMotion(strategy)}
 }
 requestAnimationFrame(turn);
}
async function playHeroMotion(name){
 stopHeroMotion();
 const token=motionToken,canvas=$('heroMotion'),card=heroCards[HERO_NAMES.indexOf(name)];
 try{
  const atlas=await motionAsset(name);
  if(token!==motionToken||name!==strategy||!$('setupScreen').classList.contains('active'))return;
  const ctx=canvas.getContext('2d'),start=performance.now();
  card.append(canvas);canvas.hidden=false;card.classList.add('motion-playing');
  function tick(now){
   if(token!==motionToken)return;
   const elapsed=now-start;
   if(elapsed>=3000||!$('setupScreen').classList.contains('active')){stopHeroMotion();return}
   const frame=Math.min(59,Math.floor(elapsed*20/1000));
   ctx.clearRect(0,0,canvas.width,canvas.height);
   ctx.drawImage(atlas,(frame%6)*360,Math.floor(frame/6)*480,360,480,0,0,360,480);
   requestAnimationFrame(tick);
  }
  tick(start);
 }catch(error){if(token===motionToken){stopHeroMotion();console.warn(error)}}
}
$('heroPrev').onclick=()=>cycleStrategy(-1);
$('heroNext').onclick=()=>cycleStrategy(1);
heroCards.forEach(card=>{
 const img=card.querySelector('img');
 img.addEventListener('error',()=>{if(card.dataset.character===strategy)$('portraitStatus').hidden=false});
 img.addEventListener('load',()=>{if(card.dataset.character===strategy)$('portraitStatus').hidden=true});
 card.onclick=()=>selectHero(card.dataset.character);
});
positionHeroRing(0);
// Shared header: each letter follows a short staggered wave as the phrase swaps.
const titlePhrases=()=>['BEAT THE HUMANOID','Stop the robot in '+(rules()?.step_limit||80)+' steps!'];
let titleIndex=0;
function setTitle(){
 const el=$('titleLetters');el.replaceChildren(...Array.from(titlePhrases()[titleIndex],(ch,i)=>{
  const span=document.createElement('span');span.textContent=ch===' '?'\u00a0':ch;span.style.setProperty('--letter',i);return span;
 }));
 $('gameTitle').classList.toggle('challenge-title',titleIndex===1);
}
setTitle();
setInterval(()=>{
 const el=$('titleLetters');el.className='wave-out';
 setTimeout(()=>{titleIndex=1-titleIndex;setTitle();el.className='wave-in'},480);
},3000);
// Prepare clips sequentially. The stills and animations are cached locally.
(async()=>{for(const name of HERO_NAMES){try{await motionAsset(name)}catch(error){console.warn(error)}}})();

function syncDifficulty(){
 const rule=rules();if(!rule)return;
 document.body.dataset.difficulty=difficulty;
 $('objectCount').dataset.max=rule.max_static_objects;$('pedCount').dataset.max=rule.max_pedestrians;
 $('objectTool').disabled=rule.max_static_objects===0;$('pedTool').disabled=rule.max_pedestrians===0;
 $('setupDifficulty').textContent=difficulty.toUpperCase();
 $('gameTitle').setAttribute('aria-label','Beat the Humanoid. Stop the robot in '+rule.step_limit+' steps!');
 setTitle();
}
function renderDifficultyOptions(){
 $('difficultyOptions').replaceChildren(...LEVELS.map(name=>{
  const rule=difficultyRules[name],b=document.createElement('button');b.type='button';b.className='difficulty-option'+(name===pendingDifficulty?' selected':'');
  b.dataset.level=name;b.setAttribute('aria-pressed',String(name===pendingDifficulty));
  const title=document.createElement('b'),desc=document.createElement('small');title.textContent=name.toUpperCase();desc.textContent=rule.step_limit+' steps · '+rule.max_observations+' scans · '+rule.max_static_objects+' objects · '+rule.max_pedestrians+' pedestrians';
  b.append(title,desc);b.onclick=()=>{pendingDifficulty=name;renderDifficultyOptions()};return b;
 }));
}
function openSettings(){if(settingsOpen||editing||starting||!rules()||!$('setupScreen').classList.contains('active'))return;pendingDifficulty=difficulty;resetDifficultyStick();settingsOpen=true;renderDifficultyOptions();$('settingsModal').hidden=false}
function closeSettings(){resetDifficultyStick();settingsOpen=false;$('settingsModal').hidden=true}
function moveDifficulty(delta){pendingDifficulty=LEVELS[(LEVELS.indexOf(pendingDifficulty)+delta+LEVELS.length)%LEVELS.length];renderDifficultyOptions()}
function changeDifficulty(delta){if(editing||starting||settingsOpen)return;setDifficulty(LEVELS[(LEVELS.indexOf(difficulty)+delta+LEVELS.length)%LEVELS.length]);}
function setDifficulty(next){
 if(next!==difficulty){
  difficulty=next;revision++;
  const before=objects.length+pedestrians.length,rule=rules();
  objects=objects.slice(0,rule.max_static_objects);pedestrians=pedestrians.slice(0,rule.max_pedestrians);
  syncDifficulty();renderEditor();$('startBtn').disabled=true;
  validate().catch(error=>toast(error.message));
  if(objects.length+pedestrians.length<before)toast('Extra obstacles removed for '+difficulty.toUpperCase()+'.');
 }
}
function applyDifficulty(){if(!settingsOpen)return;setDifficulty(pendingDifficulty);closeSettings();}
$('settingsBtn').onclick=openSettings;$('settingsApply').onclick=applyDifficulty;$('settingsCancel').onclick=closeSettings;
let resultEffectToken=0;
function stopResultEffects(){
 ++resultEffectToken;
 const motion=$('resultMotion'),confetti=$('confetti');
 motion.hidden=true;motion.getContext('2d').clearRect(0,0,motion.width,motion.height);
 confetti.hidden=true;confetti.getContext('2d').clearRect(0,0,confetti.width,confetti.height);
 $('resultPortrait').hidden=false;
}
const DEFEAT_DROP_FRAMES=30,DEFEAT_LOOP_FRAMES=24,RESULT_FPS=20;
function resultFrame(elapsed,human){
 const index=Math.max(0,Math.floor(elapsed*RESULT_FPS/1000));
 return human?(index<DEFEAT_DROP_FRAMES?index:DEFEAT_DROP_FRAMES+(index-DEFEAT_DROP_FRAMES)%DEFEAT_LOOP_FRAMES):Math.min(59,index);
}
function showResultReaction(name,human,celebrate=true){
 const token=++resultEffectToken,img=$('resultPortrait'),canvas=$('resultMotion');
 img.hidden=false;img.src='/api/portrait/'+name+'?v=8';
 $('resultHero').classList.toggle('defeated',human);
 if(human&&celebrate)burstConfetti(token);
 motionAsset(name,human?'defeat':'').then(atlas=>{
  if(token!==resultEffectToken||!$('resultScreen').classList.contains('active'))return;
  const ctx=canvas.getContext('2d'),start=performance.now();
  canvas.hidden=false;img.hidden=true;
  let lastFrame=-1;
  function tick(now){
   if(token!==resultEffectToken||!$('resultScreen').classList.contains('active'))return;
   const elapsed=now-start,frame=resultFrame(elapsed,human);
   if(frame!==lastFrame){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.drawImage(atlas,(frame%6)*360,Math.floor(frame/6)*480,360,480,0,0,canvas.width,canvas.height);
    lastFrame=frame;
   }
   if(human||elapsed<3000)requestAnimationFrame(tick);
   else{canvas.hidden=true;img.hidden=false}
  }
  tick(start);
 }).catch(error=>{
  if(token!==resultEffectToken)return;
  console.warn(error);
  canvas.hidden=true;img.hidden=false;
  if(human)img.src='/api/portrait/'+name+'?reaction=defeat&v=14';
 });
}
function burstConfetti(token){
 const canvas=$('confetti'),ctx=canvas.getContext('2d'),width=canvas.width=innerWidth,height=canvas.height=innerHeight;
 const colors=['#ffd15d','#76e8ff','#ac80ff','#66f2ae','#ff7189','#fff'];
 const particles=Array.from({length:150},(_,i)=>{
  const sign=i%2?1:-1;
  return {x:sign>0?width*.09:width*.91,y:height*.68,vx:sign*(2+Math.random()*10),vy:-7-Math.random()*12,a:Math.random()*6.28,spin:(Math.random()-.5)*.3,w:4+Math.random()*6,c:colors[i%colors.length]};
 });
 canvas.hidden=false;const start=performance.now();let previous=start;
 function tick(now){
  if(token!==resultEffectToken)return;
  const elapsed=now-start,dt=Math.min(2,(now-previous)/16.67);previous=now;
  ctx.clearRect(0,0,width,height);ctx.globalAlpha=Math.min(1,Math.max(0,(3200-elapsed)/700));
  for(const p of particles){p.x+=p.vx*dt;p.y+=p.vy*dt;p.vy+=.20*dt;p.a+=p.spin*dt;ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.a);ctx.fillStyle=p.c;ctx.fillRect(-p.w/2,-p.w/3,p.w,p.w*.65);ctx.restore()}
  ctx.globalAlpha=1;if(elapsed<3200)requestAnimationFrame(tick);else{ctx.clearRect(0,0,width,height);canvas.hidden=true}
 }
 requestAnimationFrame(tick);
}

async function openReview(){
 if(reviewOpening||starting||!$('resultScreen').classList.contains('active'))return;
 reviewOpening=true;
 try{
  const info=await api('/api/review');
  if(!$('resultScreen').classList.contains('active')||starting)return;
  reviewSteps=info.steps;
  if(!reviewSteps.length){toast('No review frames recorded.');return}
  const r=info.result;
  $('reviewMaze').textContent='MAZE '+(catalog.findIndex(m=>m.id===r.maze_id)+1);
  $('reviewStrategy').textContent=r.strategy.toUpperCase();$('reviewDifficulty').textContent=r.difficulty.toUpperCase();
  $('reviewLimit').textContent='/ '+(r.success?Math.min(r.elapsed_steps,r.step_limit):r.step_limit);$('reviewObsLimit').textContent='/ '+(r.max_observations??rules().max_observations);
  $('reviewSlider').max=String(reviewSteps.length-1);
  resetReviewHold();screen('reviewScreen');await renderReview(0);
 }catch(error){toast(error.message)}finally{reviewOpening=false}
}
async function renderReview(index){
 if(!reviewSteps.length)return;
 reviewCursor=Math.max(0,Math.min(reviewSteps.length-1,index));
 $('reviewSlider').value=String(reviewCursor);
 $('reviewFirst').disabled=$('reviewPrev').disabled=reviewCursor===0;$('reviewLast').disabled=$('reviewNext').disabled=reviewCursor===reviewSteps.length-1;
 const request=++reviewRequest,step=reviewSteps[reviewCursor];
 try{
  const s=await api('/api/review/'+step);
  if(request!==reviewRequest||!$('reviewScreen').classList.contains('active'))return;
  const m=catalog.find(x=>x.id===s.maze_id)||current();
  const robot=s.position?{position:s.position,heading_yaw:s.heading_yaw||0}:null;
  drawMap($('reviewTruth'),m,{northUp:true,objects:s.objects||[],peds:s.people||[],robot,trajectory:s.trajectory||[]});
  if(s.render_png){$('review3d').src='data:image/png;base64,'+s.render_png;$('review3d').hidden=false;$('reviewTruth').hidden=true}
  else{$('review3d').hidden=true;$('reviewTruth').hidden=false}
  drawMemory($('reviewMemory'),m,s);
  $('reviewStep').textContent=s.step;$('reviewScans').textContent=s.observations;
  const hit=s.contacts&&Object.values(s.contacts).some(v=>v>0);$('reviewContact').hidden=!hit;if(hit)$('reviewContact').textContent=contactMessage({step:s.step,contacts:s.contacts});
 }catch(error){if(request===reviewRequest)toast(error.message)}
}
function reviewSeek(state,dir,now){
 if(!dir)return {state:{dir:0,since:0,next:0},delta:0};
 if(dir!==state.dir)return {state:{dir,since:now,next:now+330},delta:dir};
 if(now<state.next)return {state,delta:0};
 const held=now-state.since;
 const stride=held>=1800?5:held>=900?2:1;
 const interval=held>=1800?80:held>=900?105:145;
 return {state:{dir,since:state.since,next:now+interval},delta:dir*stride};
}
function resetReviewHold(){reviewHold={dir:0,since:0,next:0}}
function updateReviewSeek(gp,buttons,now){
 const x=gp.axes[0]||0;
 const deadzone=reviewHold.dir?.24:.34;
 const dir=buttons.has(14)&&buttons.has(15)?0:
           buttons.has(14)?-1:buttons.has(15)?1:Math.abs(x)>deadzone?Math.sign(x):0;
 const next=reviewSeek(reviewHold,dir,now);reviewHold=next.state;
 if(next.delta)moveReview(next.delta);
}
function moveReview(delta){
 const next=Math.max(0,Math.min(reviewSteps.length-1,reviewCursor+delta));
 if(next!==reviewCursor)renderReview(next);
}
function closeReview(){
 resetReviewHold();++reviewRequest;
 if(!$('reviewScreen').classList.contains('active'))return;
 screen('resultScreen');
 if(lastResult)showResultReaction(lastResult.strategy,lastResult.winner==='HUMAN WINS',false);
}
$('reviewBtn').onclick=openReview;$('reviewBack').onclick=closeReview;
$('reviewPrev').onclick=()=>moveReview(-1);$('reviewNext').onclick=()=>moveReview(1);
$('reviewFirst').onclick=()=>{resetReviewHold();renderReview(0)};$('reviewLast').onclick=()=>{resetReviewHold();renderReview(reviewSteps.length-1)};
$('reviewSlider').oninput=()=>renderReview(Number($('reviewSlider').value));
