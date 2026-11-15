/* H2 archive UI: independent selections, no simulator or generated memory. */
'use strict';
const $=id=>document.getElementById(id);
let index,entry,record,cursor=0,playing=false,timer=null,serial=0,download=null,modelIndex=0,scheduleIndex=0,mazeIndex=0,speedIndex=1,retry=null;
const speeds=[.5,1,2,4],cache=new Map();
const eventLabels={initial_state:'INITIAL STATE',addition:'OBJECT APPEARED',relocation:'OBJECT MOVED',removal:'OBJECT DISAPPEARED',no_op:'NO CHANGE',no_change_in_saved_schedule:'NO CHANGE',saved_schedule_changes:'SAVED SCHEDULE CHANGE'};
const coords=c=>Array.isArray(c)?'('+c.join(', ')+')':'—';
const labels={move:'FORWARD / MOVE',sidestep:'SIDESTEP',retreat:'RETREAT',turn:'TURN',wait:'WAIT'};
const wrap=(i,n)=>(i%n+n)%n;
const choice=()=>H2Replay.getEntry(index,index.maps[mazeIndex].number,scheduleIndex,index.arms[modelIndex].id);
function showStatus(message,error=false,retryAction=null){retry=retryAction;const el=$('status');el.hidden=false;el.classList.toggle('error',error);el.replaceChildren(document.createTextNode(message));if(retry){const b=document.createElement('button');b.textContent='A · RETRY';b.onclick=retry;el.append(b)}}
function pause(){playing=false;clearTimeout(timer);timer=null;$('play').textContent='A · ▶ PLAY';$('play').setAttribute('aria-pressed','false')}
function rowCell(row,tag,value){const el=document.createElement(tag);el.textContent=value;row.append(el);return el}
function tableButton(label,callback){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=callback;return b}
function revealIn(container,element){
 if(!element)return;
 // Sticky thead covers the top of the scrollport. A row under it is not visible.
 if(element===element.parentElement.firstElementChild){container.scrollTop=0;return}
 const c=container.getBoundingClientRect(),e=element.getBoundingClientRect();
 const header=container.querySelector('thead');
 const top=c.top+container.clientTop+(header?.getBoundingClientRect().height||0);
 const bottom=c.top+container.clientTop+container.clientHeight;
 if(e.top<top)container.scrollTop+=e.top-top;
 else if(e.bottom>bottom)container.scrollTop+=e.bottom-bottom;
}
function refreshSelection(){
 const model=index.arms[modelIndex],map=index.maps[mazeIndex];
 $('modelDescriptionName').textContent=(modelIndex+1)+'. '+model.label;
 $('modelDescription').textContent=model.description;
 Array.from($('modelRows').children).forEach((r,i)=>{r.classList.toggle('selected',i===modelIndex);r.querySelector('button').setAttribute('aria-pressed',String(i===modelIndex))});
 revealIn($('modelScroll'),$('modelRows').children[modelIndex]);
 $('mazeLabel').textContent='MAZE '+String(map.number).padStart(2,'0')+' · '+map.family+' / '+H2Replay.schedules[scheduleIndex].label;
 $('mazeRows').replaceChildren();
 let failures=0;
 for(const [i,m] of index.maps.entries()){
  const row=document.createElement('tr');row.classList.toggle('current-maze',i===mazeIndex);
  const head=rowCell(row,'th','');head.append(tableButton(String(m.number).padStart(2,'0')+' · '+m.family,()=>select(modelIndex,scheduleIndex,i)));
  for(const [j,s] of H2Replay.schedules.entries()){
   const e=H2Replay.getEntry(index,m.number,j,model.id);if(!e.success)failures++;
   const td=rowCell(row,'td',''),b=tableButton(e.success?'✓':'✕',()=>select(modelIndex,j,i));
   b.className=(e.success?'case-success':'case-fail')+(i===mazeIndex&&j===scheduleIndex?' active-case':'');
   b.setAttribute('aria-label','Maze '+m.number+' '+s.label+' '+(e.success?'goal reached':'failed'));
   b.setAttribute('aria-pressed',String(i===mazeIndex&&j===scheduleIndex));td.append(b)
  }$('mazeRows').append(row)
 }
 $('nextFailure').disabled=failures===0;
 revealIn($('matrixScroll'),$('mazeRows').children[mazeIndex]);
}
function select(m,s,n){if(!index)return;const a=wrap(m,index.arms.length),b=wrap(s,H2Replay.schedules.length),c=wrap(n,index.maps.length);if(a===modelIndex&&b===scheduleIndex&&c===mazeIndex&&record)return;modelIndex=a;scheduleIndex=b;mazeIndex=c;refreshSelection();loadSelection()}
function nextFailure(){
 if(!index)return;const columns=H2Replay.schedules.length,start=mazeIndex*columns+scheduleIndex;
 for(let d=1;d<=index.maps.length*columns;d++){const k=wrap(start+d,index.maps.length*columns),n=Math.floor(k/columns),s=k%columns;if(!H2Replay.getEntry(index,index.maps[n].number,s,index.arms[modelIndex].id).success){select(modelIndex,s,n);return}}
}
function buildControls(){
 for(const [i,m] of index.arms.entries()){const r=document.createElement('tr');rowCell(r,'td',String(i+1)).className='model-number';const td=rowCell(r,'th','');td.append(tableButton(m.label,()=>select(i,scheduleIndex,mazeIndex)));rowCell(r,'td',String(m.goals.known));rowCell(r,'td',String(m.goals.original));rowCell(r,'td',String(m.goals.high_frequency));$('modelRows').append(r)}
 $('selection').hidden=false;refreshSelection()
}
async function loadSelection(){
 if(!index)return;
 const id=++serial;download?.abort();download=new AbortController();pause();record=null;retry=null;$('review').hidden=true;
 entry=choice();const e=entry;
 $('outcome').textContent='LOADING…';$('outcome').className='';$('finalSteps').textContent='—';$('finalScans').textContent='—';
 const params=new URLSearchParams({model:e.model.id,condition:e.condition,schedule:String(e.schedule),map:String(e.map.number)});history.replaceState(null,'','?'+params.toString());
 showStatus('LOADING RECORDED EPISODE…');
 try{
  let data=cache.get(e.path);
  if(!data){data=await H2Replay.loadReplay(index,e,download.signal);if(id!==serial)return;cache.set(e.path,data);if(cache.size>5)cache.delete(cache.keys().next().value)}
  if(id!==serial)return;
  record=data;cursor=0;retry=null;$('status').hidden=true;$('review').hidden=false;
  $('outcome').textContent=e.success?'GOAL REACHED':'NOT REACHED';$('outcome').className=e.success?'success':'fail';
  $('finalSteps').textContent=data.metrics.steps+' / '+e.stepLimit;$('finalScans').textContent=data.metrics.paidScans+' / '+e.scanLimit;
  $('contactWarning').hidden=data.metrics.unwantedContacts===0;$('contactWarning').textContent='WARNING · UNWANTED CONTACTS ('+data.metrics.unwantedContacts+')';
  $('archiveNote').hidden=e.parity!=='FIRST_TIME_FIT72_EVALUATION';$('archiveNote').textContent='Known FIT72: first-time evaluation (no prior identity-matched result).';
  $('original').href=H2Replay.originalURL(e);$('slider').max=String(record.frames.length-1);render(0);
 }catch(error){if(id===serial&&error.name!=='AbortError'){$('outcome').textContent='UNAVAILABLE';showStatus(error.message,true,loadSelection)}}
}
const colors={free:'#152330',unknown:'#485364',memoryFree:'#174247',memoryOccupied:'#9a6250',object:'#f19a43',ped:'#f26970',robot:'#64b4ff',goal:'#ffd074',event:'#fff2bb'};
function draw(canvas,frame,isMemory){
 const ctx=canvas.getContext('2d'),r=record.replay,w=r.grid.width,h=r.grid.height;
 if(isMemory&&!frame.memory){ctx.fillStyle='#0b111a';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#aabccc';ctx.font='24px system-ui';ctx.textAlign='center';ctx.fillText('SPATIAL MEMORY NOT RECORDED',canvas.width/2,canvas.height/2);return}
 const inset=9,cell=Math.min((canvas.width-2*inset)/w,(canvas.height-2*inset)/h),x0=(canvas.width-w*cell)/2,y0=(canvas.height-h*cell)/2;
 const point=c=>[x0+(c[0]+.5)*cell,y0+(h-c[1]-.5)*cell];
 const box=c=>[x0+c[0]*cell,y0+(h-1-c[1])*cell];
 function fill(c,color,pad=1){const [x,y]=box(c);ctx.fillStyle=color;ctx.fillRect(x+pad,y+pad,cell-2*pad,cell-2*pad)}
 function ring(c,color,rad=.34){const [x,y]=point(c);ctx.beginPath();ctx.arc(x,y,cell*rad,0,Math.PI*2);ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.stroke()}
 function line(path,color,width,dashes=[]){if(path.length<2)return;ctx.beginPath();path.forEach((c,i)=>{const p=point(c);i?ctx.lineTo(...p):ctx.moveTo(...p)});ctx.setLineDash(dashes);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineJoin='round';ctx.lineCap='round';ctx.stroke();ctx.setLineDash([])}
 ctx.fillStyle='#0b111a';ctx.fillRect(0,0,canvas.width,canvas.height);
 const wall=({R:'#355c88',BP:'#327d70',M:'#76529b'})[r.map_family]||'#355c88';
 // Occupancy includes pedestrians. Use explicit recorded object cells for orange fill.
 const objectCells=new Set((frame.objects_after||[]).map(o=>o.cell.join(',')));
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=y*w+x,c=[x,y],v=frame.memory?.[i];
  fill(c,isMemory?(v===-1?colors.unknown:v===0?colors.memoryFree:colors.memoryOccupied):record.walls.has(c.join(','))?wall:objectCells.has(c.join(','))?colors.object:colors.free,.65);
 }
 if(isMemory&&frame.observation_granted){
  ctx.strokeStyle='#53dceab0';ctx.lineWidth=1.5;
  for(const cellData of frame.observed_cells_xy_value||[]){const [x,y]=box(cellData);ctx.strokeRect(x+2,y+2,cell-4,cell-4)}
 }
 if(!isMemory){
  for(const o of frame.objects_after){fill(o.cell,colors.object,cell*.18);const [x,y]=point(o.cell);ctx.fillStyle='#8a4b1b';ctx.fillRect(x-cell*.15,y-cell*.15,cell*.3,cell*.3)}
  const ev=frame.event,from=ev.from_cell,to=ev.to_cell;for(const change of ev.changes||[]){const c=change.cell||change.from_cell||change.to_cell;if(c)ring(c,colors.event,.43);if(change.to)ring(change.to,colors.event,.43)}
  if(from){ctx.setLineDash([4,3]);ring(from,colors.event,.43);ctx.setLineDash([])}
  if(to)ring(to,colors.event,.43);
  if(from&&to){line([from,to],colors.event,1.5,[5,4]);const [x,y]=point(to),[fx,fy]=point(from),a=Math.atan2(y-fy,x-fx);ctx.strokeStyle=colors.event;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x-8*Math.cos(a-.45),y-8*Math.sin(a-.45));ctx.lineTo(x,y);ctx.lineTo(x-8*Math.cos(a+.45),y-8*Math.sin(a+.45));ctx.stroke()}
 }
 const trajectory=record.frames.slice(0,cursor+1).map(f=>f.robot_position_after_action_xy);
 line(trajectory,'#64b4ffaa',Math.max(2,cell*.09));
 ring(r.start_xy,'#9ec8e5',.30);ring(r.goal_xy,colors.goal,.38);
 const [gx,gy]=point(r.goal_xy);ctx.fillStyle=colors.goal;ctx.beginPath();ctx.arc(gx,gy,cell*.15,0,Math.PI*2);ctx.fill();
 const [rx,ry]=point(frame.robot_position_after_action_xy);ctx.save();ctx.translate(rx,ry);ctx.rotate(-frame.robot_heading_after_action_rad);ctx.fillStyle=colors.robot;ctx.strokeStyle='#c9ebff';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(cell*.38,0);ctx.lineTo(-cell*.25,-cell*.23);ctx.lineTo(-cell*.18,0);ctx.lineTo(-cell*.25,cell*.23);ctx.closePath();ctx.fill();ctx.stroke();ctx.restore();
 // Draw pedestrians as a solid red circle, matching the legend, above the path.
 if(!isMemory)for(const ped of frame.pedestrians_xy){const [x,y]=point(ped.cell);ctx.beginPath();ctx.arc(x,y,cell*.28,0,Math.PI*2);ctx.fillStyle=colors.ped;ctx.fill()}
}

function render(value){
 if(!record)return;cursor=Math.max(0,Math.min(record.frames.length-1,Number(value)||0));const f=record.frames[cursor],ev=f.event;
 $('slider').value=String(cursor);$('first').disabled=$('prev').disabled=cursor===0;$('next').disabled=$('last').disabled=cursor===record.frames.length-1;
 $('stepCount').textContent=f.step+' / '+record.metrics.steps;$('scanCount').textContent=f.paid_observation_count+' / '+entry.scanLimit;
 $('scanState').textContent=f.observation_granted?'PAID SCAN GRANTED':f.observation_requested?'SCAN REQUESTED · NOT GRANTED':'NO PAID SCAN';
 $('eventType').textContent=eventLabels[ev.event_type]||ev.event_type;
 $('eventDetail').textContent=ev.event_type==='initial_state'?'Initial objects: '+f.objects_after.length:ev.changes?.length?ev.changes.map(c=>[c.action||c.event_type,c.cell?coords(c.cell):c.from_cell?coords(c.from_cell):'',c.to?coords(c.to):c.to_cell?coords(c.to_cell):''].filter(Boolean).join(' ')).join(' · '):[ev.object_id,ev.from_cell?'FROM '+coords(ev.from_cell):'',ev.to_cell?'TO '+coords(ev.to_cell):'',ev.object_count_after!=null?'Objects: '+ev.object_count_before+' → '+ev.object_count_after:''].filter(Boolean).join(' · ');
 const action=f.executed_action;
 $('action').textContent=Array.isArray(action)?(labels[action[0]]||String(action[0]).toUpperCase()):(f.step===0?'INITIAL POSE':String(action??'NO ACTION').toUpperCase());
 const rejection=f.selected_action_shield_rejection,intervention=f.emergency_safety_intervention;
 $('safety').textContent=[Array.isArray(action)&&action[0]!=='wait'?'Action: '+(Array.isArray(action[1])?coords(action[1]):String(action[1]??'')):'',intervention?'Safety: '+(intervention.reason||'intervention'):f.emergency_safety_scan?'Independent safety scan':'No safety scan',rejection?.rejected?'Shield rejected: '+(rejection.reason||'action'):''].filter(Boolean).join(' · ');
 $('memoryDetail').textContent=f.memory?f.memory.reduce((s,v)=>s+(v!==-1?1:0),0)+' / '+f.memory.length+' cells known':'Not recorded';
 const hits=Object.values(f.unwanted_contacts||{}).reduce((s,n)=>s+Number(n),0);$('contactDetail').textContent=hits?'WARNING · UNWANTED CONTACTS AT THIS STEP: '+hits:f.goal_reached?'Goal reached':'';$('contactDetail').classList.toggle('failure-color',hits>0);
 draw($('truth'),f,false);draw($('memory'),f,true);
}
function seek(value){pause();render(value)}
function startPlayback(){if(!record)return;if(cursor===record.frames.length-1)render(0);playing=true;$('play').textContent='A · Ⅱ PAUSE';$('play').setAttribute('aria-pressed','true');scheduleTick()}
function scheduleTick(){clearTimeout(timer);if(!playing)return;timer=setTimeout(()=>{if(!playing||!record)return;if(cursor>=record.frames.length-1){pause();return}render(cursor+1);if(cursor>=record.frames.length-1)pause();else scheduleTick()},200/speeds[speedIndex])}
function toggle(){if(retry){retry();return}playing?pause():startPlayback()}
function cycleSpeed(){speedIndex=wrap(speedIndex+1,speeds.length);$('speed').textContent='SPEED '+speeds[speedIndex]+'×';if(playing)scheduleTick()}
function back(){location.href='./'}
let fullscreenPending=false;
function fullscreenElement(){return document.fullscreenElement||document.webkitFullscreenElement||null}
function syncFullscreen(){
 const active=!!fullscreenElement(),b=$('fullscreenBtn');
 b.setAttribute('aria-pressed',String(active));
 b.setAttribute('aria-label',active?'Exit fullscreen':'Enter fullscreen');
 b.title=(active?'Exit fullscreen':'Fullscreen')+' (Xbox View button)';
}
async function fullscreen(){
 if(fullscreenPending)return;
 fullscreenPending=true;let blocked=false;
 try{
  if(fullscreenElement()){const exit=document.exitFullscreen||document.webkitExitFullscreen;if(!exit)throw Error('Fullscreen exit unavailable');await exit.call(document)}
  else{const root=document.documentElement,enter=root.requestFullscreen||root.webkitRequestFullscreen;if(!enter)throw Error('Fullscreen unavailable');await enter.call(root)}
 }catch{blocked=true}finally{fullscreenPending=false;syncFullscreen();if(blocked)$('fullscreenBtn').title='Fullscreen blocked by browser; click to retry'}
}
document.addEventListener('fullscreenchange',syncFullscreen);
document.addEventListener('webkitfullscreenchange',syncFullscreen);
syncFullscreen();
$('back').onclick=back;$('fullscreenBtn').onclick=fullscreen;$('modelNext').onclick=()=>select(modelIndex+1,scheduleIndex,mazeIndex);$('nextFailure').onclick=nextFailure;
$('first').onclick=()=>seek(0);$('prev').onclick=()=>seek(cursor-1);$('next').onclick=()=>seek(cursor+1);$('last').onclick=()=>record&&seek(record.frames.length-1);
$('slider').oninput=e=>seek(e.target.value);$('play').onclick=toggle;$('speed').onclick=cycleSpeed;
window.addEventListener('keydown',e=>{
 if(e.target.tagName==='INPUT'&&e.key.startsWith('Arrow')&&!e.shiftKey)return;
 const k=e.key.toLowerCase();
 if(e.shiftKey&&k.startsWith('arrow')){e.preventDefault();moveMatrix(k.slice(5));return}
 const actions={arrowleft:()=>seek(cursor-1),arrowright:()=>seek(cursor+1),arrowup:()=>select(modelIndex-1,scheduleIndex,mazeIndex),arrowdown:()=>select(modelIndex+1,scheduleIndex,mazeIndex),x:()=>select(modelIndex+1,scheduleIndex,mazeIndex),y:()=>select(modelIndex,scheduleIndex+1,mazeIndex),'[':()=>select(modelIndex,scheduleIndex,mazeIndex-1),']':()=>select(modelIndex,scheduleIndex,mazeIndex+1),f:nextFailure,home:()=>seek(0),end:()=>record&&seek(record.frames.length-1),' ':toggle,s:cycleSpeed,escape:back,b:back};
 if(actions[k]){e.preventDefault();if(!e.repeat||k.startsWith('arrow'))actions[k]()}
});
function stickDirection(x,y){
 return Math.max(Math.abs(x),Math.abs(y))>.4?(Math.abs(x)>=Math.abs(y)?(x<0?'left':'right'):(y<0?'up':'down')):'';
}
function moveMatrix(dir){
 if(dir==='up'||dir==='down')select(modelIndex,scheduleIndex,mazeIndex+(dir==='up'?-1:1));
 else if(dir==='left'||dir==='right')select(modelIndex,scheduleIndex+(dir==='left'?-1:1),mazeIndex);
}
function moveMain(dir){
 if(dir==='up'||dir==='down')select(modelIndex+(dir==='up'?-1:1),scheduleIndex,mazeIndex);
 else if(dir==='left'||dir==='right')seek(cursor+(dir==='left'?-1:1));
}
function repeatDirection(state,dir,now,move,interval){
 if(dir&&(dir!==state.dir||now>=state.next)){move(dir);state.next=now+(dir!==state.dir?330:interval)}
 state.dir=dir;
}
let previous=null,mainHold={dir:'',next:0},matrixHold={dir:'',next:0};
function gamepad(now){
 const pad=[...(navigator.getGamepads?.()||[])].find(Boolean);
 const status=$('padStatus');status.classList.toggle('connected',!!pad);status.setAttribute('aria-label',pad?'Controller connected':'Controller disconnected');
 if(pad){
  const buttons=new Set(pad.buttons.flatMap((b,i)=>b.pressed||b.value>.55?[i]:[]));
  const edge=i=>previous!==null&&buttons.has(i)&&!previous.has(i);
  if(edge(1)){back();return}
  if(edge(8))fullscreen();
  if(edge(0))toggle();else if(edge(2))select(modelIndex+1,scheduleIndex,mazeIndex);else if(edge(3))select(modelIndex,scheduleIndex+1,mazeIndex);else if(edge(4))select(modelIndex,scheduleIndex,mazeIndex-1);else if(edge(5))select(modelIndex,scheduleIndex,mazeIndex+1);else if(edge(6))seek(0);else if(edge(7)&&record)seek(record.frames.length-1);else if(edge(9))nextFailure();else if(edge(11))cycleSpeed();
  const left=buttons.has(12)?'up':buttons.has(13)?'down':buttons.has(14)?'left':buttons.has(15)?'right':stickDirection(pad.axes[0]||0,pad.axes[1]||0);
  const right=stickDirection(pad.axes[2]||0,pad.axes[3]||0);
  if(previous){
   // The right stick navigates the matrix; the left stick / D-pad retain the model and step controls.
   repeatDirection(matrixHold,right,now,moveMatrix,160);
   repeatDirection(mainHold,right?'':left,now,moveMain,left==='up'||left==='down'?200:95)
  }
  previous=buttons
 }else{previous=null;mainHold.dir=matrixHold.dir='';mainHold.next=matrixHold.next=0}
 requestAnimationFrame(gamepad)
}
async function initialize(){try{
 showStatus('LOADING EXPERIMENT INDEX…');index=await H2Replay.loadIndex();
 const p=new URLSearchParams(location.search),m=index.arms.findIndex(a=>a.id===p.get('model')),n=index.maps.findIndex(a=>String(a.number)===p.get('map'));
 modelIndex=m<0?0:m;mazeIndex=n<0?0:n;const s=H2Replay.schedules.findIndex(a=>a.condition===(p.get('condition')||'high_frequency')&&String(a.number)===p.get('schedule'));scheduleIndex=s<0?2:s;
 buildControls();await loadSelection()
 }catch(error){showStatus(error.message,true,()=>location.reload())}}
 requestAnimationFrame(gamepad);initialize();
