/* Read-only replay reader for the pinned H2 comprehensive benchmark. */
'use strict';
(function(root){
 const sourceRepo='fujitamasahir/humanoid-spatial-memory',sourceCommit='3b208befeb268cb2ae789add7deaaf859abcfc5a';
 const offlineSource=root.document?.querySelector('meta[name="h2-archive-base"]')?.content;
 const source=offlineSource||'https://raw.githubusercontent.com/'+sourceRepo+'/'+sourceCommit+'/';
 const folder='results/phase2_mujoco/h2_comprehensive_benchmark_v1/';
 const hfFolder='results/phase2_mujoco/h2_high_frequency_dynamics_v1/';
 const recoveryFolder='results/phase2_mujoco/h2_full_spatial_memory_replay_v1/';
 const schedules=[{condition:'known',number:0,label:'Known 0',short:'K0'},{condition:'known',number:1,label:'Known 1',short:'K1'},{condition:'original',number:0,label:'Low-frequency 0',short:'L0'},{condition:'original',number:1,label:'Low-frequency 1',short:'L1'},{condition:'high_frequency',number:0,label:'High-frequency 0',short:'H0'},{condition:'high_frequency',number:1,label:'High-frequency 1',short:'H1'}];
 const key=(condition,model,identity,schedule)=>[condition,model,identity,Number(schedule)].join('|');
 const base64=value=>Uint8Array.from(atob(value),c=>c.charCodeAt(0));
 function decodeMemory(value,w,h){const b=base64(value),n=w*h;if(b.length!==Math.ceil(n/4))throw Error('Invalid memory length');return Array.from({length:n},(_,i)=>{const v=(b[i>>2]>>(2*(i%4)))&3;if(v===3)throw Error('Invalid memory value');return v-1})}
 function decodeBits(value,w,h){const b=base64(value),n=w*h;if(b.length!==Math.ceil(n/8))throw Error('Invalid truth length');return Array.from({length:n},(_,i)=>(b[i>>3]>>(i%8))&1)}
 function csv(s){
  const rows=[];let row=[],field='',quoted=false;
  for(let i=0;i<s.length;i++){const c=s[i];if(c==='"'){if(quoted&&s[i+1]==='"'){field+='"';i++}else quoted=!quoted}else if(c===','&&!quoted){row.push(field);field=''}else if(c==='\n'&&!quoted){row.push(field.replace(/\r$/,''));if(row.some(Boolean))rows.push(row);row=[];field=''}else field+=c}
  if(field||row.length){row.push(field.replace(/\r$/,''));rows.push(row)}
  if(quoted||!rows.length)throw Error('Invalid benchmark CSV');
  const header=rows.shift();return rows.map(r=>{if(r.length!==header.length)throw Error('Invalid CSV row width');return Object.fromEntries(header.map((h,i)=>[h,r[i]]))})
 }
 async function fetchChecked(url,signal){const res=await fetch(url,{signal});if(!res.ok){if(offlineSource&&res.status===503)throw Error('Local research archive unavailable. Run the exhibition archive preflight in the README.');throw Error('Archive request failed (HTTP '+res.status+')')}return res}
 const isTrue=value=>value===true||String(value).toLowerCase()==='true'||value==='1';
 function buildIndex(local,manifest,modelRows,failureRows,recoveryRows,knownSummary,correctionRows,descriptions){
  if(manifest.schema_version!=='h2_comprehensive_replay_index_v1'||manifest.entries.length!==7776||local.maps.length!==36||recoveryRows.length!==4752)throw Error('Unexpected H2 archive size');
  const arms=modelRows.filter(r=>r.condition==='original'&&Number(r.episodes)>0).map(r=>({id:r.model_id,label:r.display_name,goals:{},episodes:72,description:descriptions[r.model_id]?.description}));
  if(arms.length!==54||new Set(arms.map(a=>a.id)).size!==54||arms[0].id!=='periodic4'||arms.some(a=>!a.description||a.description.split(/\s+/).length>50))throw Error('Invalid 54-model registry');
  const knownRows=recoveryRows.filter(r=>r.dataset==='fit72_known'),unseenRows=recoveryRows.filter(r=>r.dataset==='h2_unseen');
  if(knownRows.length!==3888||unseenRows.length!==864)throw Error('Missing recovery rows');
  const knownIds=[...new Set(knownRows.map(r=>r.map_identity))];
  // Original FIT72 ordering: R, BP, M, each ordered by the admitted checkpoint index/seed.
  const families=['R','BP','M'];
  const knownMaps=families.flatMap(f=>knownIds.filter(id=>id.split(':').at(-2)===f).sort((a,b)=>Number(a.split(':').at(-1))-Number(b.split(':').at(-1))));
  const maps=local.maps.map(({number,identity,family},i)=>({number,identity,family,knownIdentity:knownMaps[i]}));
  if(knownIds.length!==36||knownMaps.length!==36||maps.some(m=>!m.knownIdentity||m.knownIdentity.split(':').at(-2)!==m.family||!/^\S+:fit:(R|BP|M):\d+$/.test(m.knownIdentity)))throw Error('Invalid FIT72 map catalog');
  const identities=new Set(maps.map(m=>m.identity)),knownSet=new Set(knownMaps),models=new Set(arms.map(a=>a.id)),byKey=new Map(),failures=new Map();
  const validPath=e=>/^results\/phase2_mujoco\/[A-Za-z0-9_./-]+\.json\.gz$/.test(e.path)&&!e.path.includes('..')&&/^[0-9a-f]{64}$/.test(e.sha256);
  for(const e of manifest.entries){
   const k=key(e.condition,e.model_id,e.world_identity,e.schedule);
   if(byKey.has(k)||!models.has(e.model_id)||!identities.has(e.world_identity)||!['original','high_frequency'].includes(e.condition)||![0,1].includes(e.schedule)||e.seed!==42||!['trace','replay'].includes(e.payload_type)||!validPath(e))throw Error('Invalid historical episode index');
   byKey.set(k,e)
  }
  for(const f of failureRows){const k=key(f.condition,f.model_id,f.world_identity,f.schedule);if(!byKey.has(k)||failures.has(k))throw Error('Invalid historical failure index');failures.set(k,f)}
  // The v3 reconciliation corrects B+Age paths and metrics. Use the corrected CSV,
  // not the older summary's initial B+C-as-B+Age row or v3's copied outcome metadata.
  const corrections=new Map(correctionRows.map(r=>[key('known',r.model_id,r.map_identity,r.schedule),r]));
  if(corrections.size!==72||correctionRows.some(r=>r.model_id!=='b_age'||r.parity_status!=='PASS_EXACT_TRACE_AND_METRIC_SIGNATURE'))throw Error('Missing corrected B+Age records');
  let replaced=0,added=0,firstTime=0,exactKnown=0;
  for(const row of recoveryRows){
   const condition=row.dataset==='fit72_known'?'known':row.dataset==='h2_unseen'?'original':null;
   const identity=row.map_identity,schedule=Number(row.schedule),success=isTrue(row.success);
   const e={condition,model_id:row.model_id,world_identity:identity,schedule,seed:Number(row.seed),path:recoveryFolder+row.path,sha256:row.sha256,payload_type:'replay',recovered:true,success,steps:Number(row.steps),paidScans:Number(row.paid_observations),contacts:Number(row.unwanted_contact_pairs),bytes:Number(row.bytes),parity:row.parity_status};
   const k=key(condition,e.model_id,identity,schedule);
   if(!models.has(e.model_id)||!(condition==='known'?knownSet.has(identity):condition==='original'&&identities.has(identity))||row.condition!=='original'||e.seed!==42||![0,1].includes(schedule)||!validPath(e)||!Number.isInteger(e.steps)||e.steps<0||e.steps>80||Number(row.frames)!==e.steps+1||!Number.isInteger(e.paidScans)||e.paidScans<0||e.paidScans>20||!Number.isInteger(e.contacts)||e.contacts<0||!Number.isInteger(e.bytes)||e.bytes<=0||!/^(True|False|true|false|0|1)$/.test(String(row.success)))throw Error('Invalid recovered replay: '+k);
   if(condition==='original'){
    const old=byKey.get(k);
    if(!old||old.payload_type!=='trace'||e.parity!=='PASS_EXACT_TRACE_AND_METRIC_SIGNATURE'||success===failures.has(k))throw Error('Recovered unseen outcome mismatch: '+k);
    replaced++;
   }else{
    if(byKey.has(k))throw Error('Duplicate known replay: '+k);
    if(e.parity==='FIRST_TIME_FIT72_EVALUATION')firstTime++;
    else if(e.parity==='PASS_EXACT_TRACE_AND_METRIC_SIGNATURE')exactKnown++;
    else throw Error('Unreconciled known replay: '+k);
    if(e.model_id==='b_age'){
     const c=corrections.get(k);
     if(!c||row.path!==c.recovery_path||e.sha256!==c.recovery_sha256||success!==isTrue(c.recovery_success)||e.steps!==Number(c.recovery_steps)||e.paidScans!==Number(c.recovery_observations))throw Error('B+Age correction mismatch: '+k)
    }
    if(!success)failures.set(k,e);
    added++;
   }
   byKey.set(k,e)
  }
  if(replaced!==864||added!==3888||firstTime!==1296||exactKnown!==2592||byKey.size!==11664||[...byKey.values()].some(e=>e.payload_type!=='replay'))throw Error('Incomplete full-memory replay coverage');
  for(const model of arms)for(const condition of ['known','original','high_frequency']){
   let goals=0;
   for(const map of maps)for(const schedule of [0,1]){
    const k=key(condition,model.id,condition==='known'?map.knownIdentity:map.identity,schedule);
    if(!byKey.has(k))throw Error('Missing experiment: '+k);
    if(!failures.has(k))goals++;
   }
   const summary=condition==='known'?knownSummary.find(r=>r.model_id===model.id):modelRows.find(r=>r.condition===condition&&r.model_id===model.id);
   const expected=condition==='known'?(model.id==='b_age'?correctionRows.filter(r=>isTrue(r.recovery_success)).length:Number(summary?.goal_completions)):Number(summary?.goals);
   if(!summary||Number(summary.episodes)!==72||expected!==goals)throw Error('Outcome table mismatch for '+condition+' '+model.id);
   model.goals[condition]=goals;
  }
  if(arms.reduce((s,m)=>s+m.goals.original,0)!==2968||arms.reduce((s,m)=>s+m.goals.high_frequency,0)!==2949)throw Error('Benchmark totals mismatch');
  return {maps,arms,byKey,failures}
 }
 
 // Overlay only the 144 corrected unseen B+Age replays. Known B+Age is already
 // reconciled by the original reader. The final model summary is independently
 // checked for all 54 models and all three conditions.
 const finalCommit='56ad4a4f474c6194783a02c2a949d6d61bb3ab71';
 const finalFolder='results/phase2_mujoco/h2_final_benchmark_reconciliation_v1/';
 const finalSource=offlineSource||'https://raw.githubusercontent.com/'+sourceRepo+'/'+finalCommit+'/';
 function reconcileFinal(index,journal,summary){
  const conditions={known_low_frequency:'known',unseen_low_frequency:'original',unseen_high_frequency:'high_frequency'};
  const rows=journal.trim().split(/\r?\n/).map(line=>JSON.parse(line).record);
  const replaced=new Set();
  if(rows.length!==144)throw Error('Missing corrected unseen B+Age journal');
  for(const r of rows){
   const condition=conditions[r.condition],k=key(condition,'b_age',r.map_identity,r.schedule);
   const old=index.byKey.get(k);
   if(!old||condition==='known'||replaced.has(k)||r.event!=='episode_committed'||r.model_id!=='b_age'||r.seed!==42||typeof r.success!=='boolean'||!Number.isInteger(r.steps)||r.steps<0||r.steps>80||!Number.isInteger(r.observations)||r.observations<0||r.observations>20||!Number.isInteger(r.bytes)||r.bytes<=0||r.unwanted_contacts!==0||!(/^[0-9a-f]{64}$/).test(r.sha256)||!(/^corrected_b_age_unseen_v1\/episodes\/(unseen_low_frequency|unseen_high_frequency)\/[A-Za-z0-9_-]+\.json\.gz$/).test(r.path)||!r.path.startsWith('corrected_b_age_unseen_v1/episodes/'+r.condition+'/'))throw Error('Invalid B+Age correction: '+k);
   const e={...old,condition,model_id:'b_age',world_identity:r.map_identity,schedule:r.schedule,seed:42,path:finalFolder+r.path,sha256:r.sha256,payload_type:'replay',recovered:true,success:r.success,steps:r.steps,paidScans:r.observations,contacts:r.unwanted_contacts,bytes:r.bytes,finalCorrection:true};
   index.byKey.set(k,e);index.failures.delete(k);if(!r.success)index.failures.set(k,e);replaced.add(k);
  }
  if(replaced.size!==144||index.byKey.size!==11664||summary.length!==162)throw Error('Final dataset coverage mismatch');
  const seen=new Set();
  for(const r of summary){
   const condition=conditions[r.evaluation_condition],model=index.arms.find(m=>m.id===r.model_id);
   const summaryKey=condition+'|'+r.model_id;
   if(!model||!condition||seen.has(summaryKey)||Number(r.episodes)!==72||Number(r.unwanted_contact_episodes)!==0)throw Error('Invalid final summary');
   let goals=0;
   for(const map of index.maps)for(const n of [0,1]){
    const k=key(condition,model.id,condition==='known'?map.knownIdentity:map.identity,n);
    if(!index.byKey.has(k))throw Error('Missing final episode: '+k);
    if(!index.failures.has(k))goals++;
   }
   if(goals!==Number(r.goal_completions))throw Error('Final outcome mismatch: '+summaryKey);
   model.goals[condition]=goals;seen.add(summaryKey);
  }
  return index;
 }

 async function loadIndex(){
  const [local,manifest,models,failures,recovery,known,corrections,descriptions,journal,finalSummary]=await Promise.all([
   fetchChecked('./h2/index.json').then(r=>r.json()),
   fetchChecked(source+folder+'combined_dataset/replay_index.json').then(r=>r.json()),
   fetchChecked(source+folder+'analysis/model_summary.csv').then(r=>r.text()).then(csv),
   fetchChecked(source+folder+'analysis/failure_cases.csv').then(r=>r.text()).then(csv),
   fetchChecked(source+recoveryFolder+'replay_index_reconciled.csv').then(r=>r.text()).then(csv),
   fetchChecked(source+recoveryFolder+'fit72_model_summary.csv').then(r=>r.text()).then(csv),
   fetchChecked(source+recoveryFolder+'fit72_b_age_correction_validation.csv').then(r=>r.text()).then(csv),
   fetchChecked('./h2/model-descriptions.json?v=1').then(r=>r.json()),
   fetchChecked(finalSource+finalFolder+'corrected_b_age_unseen_v1/journal.jsonl').then(r=>r.text()),
   fetchChecked(finalSource+finalFolder+'final_model_summary.csv').then(r=>r.text()).then(csv)
  ]);
  return reconcileFinal(buildIndex(local,manifest,models,failures,recovery,known,corrections,descriptions),journal,finalSummary)
 }
 function getEntry(index,mapNumber,scheduleIndex,arm){
  const row=index.maps.find(m=>m.number===Number(mapNumber)),model=index.arms.find(a=>a.id===arm),choice=schedules[scheduleIndex];
  if(!row||!model||!choice)throw Error('Unknown selection');
  const map={...row,identity:choice.condition==='known'?row.knownIdentity:row.identity};
  const k=key(choice.condition,arm,map.identity,choice.number),e=index.byKey.get(k);
  if(!e)throw Error('Missing replay');
  return {...e,map,model,choice,schedule:choice.number,success:!index.failures.has(k),scanLimit:20,stepLimit:80}
 }
 const rawURL=entry=>(entry.finalCorrection?finalSource:source)+entry.path;
 const originalURL=entry=>offlineSource?rawURL(entry):'https://github.com/'+sourceRepo+'/blob/'+(entry.finalCorrection?finalCommit:sourceCommit)+'/'+entry.path;
 const mapCache=new Map();
 async function loadMap(entry,signal){
  const n=entry.map.number,p=hfFolder+'maps/map_'+String(n).padStart(2,'0')+'_'+entry.map.family+'.json';
  if(mapCache.has(n))return mapCache.get(n);
  const m=await fetchChecked(source+p,signal).then(r=>r.json());
  if(m.identity!==entry.map.identity||m.geometry.width!==25||m.geometry.height!==25)throw Error('Saved map identity mismatch');
  mapCache.set(n,m);return m
 }
 function outcome(body,entry){
  const r=body.row;if(!r||r.world_identity!==entry.map.identity||Number(r.schedule)!==entry.schedule||Number(r.seed)!==entry.seed||Boolean(r.success)!==entry.success)throw Error('Recorded episode identity/outcome mismatch');
  const steps=Number(r.elapsed_steps),paidScans=Number(r.observation_count),unwantedContacts=Number(r.g1_unwanted_contact_pairs);
  if(!Number.isInteger(steps)||steps<0||steps>entry.stepLimit||!Number.isInteger(paidScans)||paidScans<0||paidScans>entry.scanLimit||!Number.isInteger(unwantedContacts)||unwantedContacts<0)throw Error('Invalid episode metrics');
  if(entry.recovered&&(steps!==entry.steps||paidScans!==entry.paidScans||unwantedContacts!==entry.contacts))throw Error('Recovered replay metrics mismatch');
  return {steps,paidScans,unwantedContacts}
 }
 const cells=(w,h)=>Array.from({length:w*h},(_,i)=>[i%w,Math.floor(i/w)]);
 function recordedReplay(body,entry,metrics){
  const r=body.replay,w=r?.grid?.width,h=r?.grid?.height;
  if(r?.schema_version!=='1.0.0'||r.episode_key?.join('|')!==[entry.map.identity,entry.schedule,entry.model.id,entry.seed].join('|')||w!==25||h!==25||r.map_family!==entry.map.family||r.steps.length!==metrics.steps+1)throw Error('Replay identity or frame count mismatch');
  const validCell=c=>Array.isArray(c)&&c.length===2&&c.every(Number.isInteger)&&c[0]>=0&&c[0]<w&&c[1]>=0&&c[1]<h;
  if(!validCell(r.start_xy)||!validCell(r.goal_xy)||!r.static_walls_xy.every(validCell))throw Error('Invalid maze geometry');
  let paid=0,contacts=0;
  const frames=r.steps.map((f,i)=>{
   const event=f.event;
   if(f.step!==i||event?.step!==i||!validCell(f.robot_position_after_action_xy)||!Number.isFinite(f.robot_heading_after_action_rad))throw Error('Invalid recorded frame '+i);
   if(entry.condition==='high_frequency'&&(i===0?event.event_type!=='initial_state':!['addition','relocation','removal','no_op'].includes(event.event_type)))throw Error('Invalid high-frequency event');
   if(!f.objects_after.every(o=>validCell(o.cell))||!f.pedestrians_xy.every(o=>validCell(o.cell)))throw Error('Invalid hazards');
   if(f.paid_observation_count!==paid+Number(f.observation_granted)||f.paid_observation_count>entry.scanLimit)throw Error('Paid scan mismatch');
   paid=f.paid_observation_count;contacts+=Object.values(f.unwanted_contacts||{}).reduce((s,n)=>s+Number(n),0);
   const packed=f.spatial_memory_end_of_step_packed_2bit_base64||f.spatial_memory_ternary_packed_2bit_base64;
   const memory=packed?decodeMemory(packed,w,h):Array.isArray(f.spatial_memory_ternary_y_major)?f.spatial_memory_ternary_y_major.flat():null;
   const truth=f.ground_truth_static_and_object_occupancy_packed_bits_base64?decodeBits(f.ground_truth_static_and_object_occupancy_packed_bits_base64,w,h):Array.isArray(f.ground_truth_static_and_object_occupancy_y_major)?f.ground_truth_static_and_object_occupancy_y_major.flat():null;
   if(entry.recovered&&(!memory||!f.spatial_memory_end_of_step_packed_2bit_base64))throw Error('Recovered frame lacks full spatial memory: '+i);
   return {...f,memory,truth}
  });
  if(paid!==metrics.paidScans||contacts!==metrics.unwantedContacts||Boolean(frames.at(-1).goal_reached)!==entry.success)throw Error('Final frame mismatch');
  return {replay:r,frames,walls:new Set(r.static_walls_xy.map(c=>c.join(','))),metrics,legacy:false}
 }
 // The historical 12-model trace stores pose, actions, paid scan grants and contacts,
 // but not per-step memory. Geometry comes ONLY from the corresponding saved map/schedule.
 // Do not synthesize memory or pretend scheduled object positions are newly recorded.
 function historicalTrace(body,entry,metrics,map){
  const r=body.trace,w=map.geometry.width,h=map.geometry.height,s=map.world.schedules[entry.schedule];
  if(r?.key?.[0]!==entry.map.identity||Number(r.key[1])!==entry.schedule||Number(r.key[3])!==entry.seed||r.steps.length!==metrics.steps+1)throw Error('Historical trace identity mismatch');
  const free=new Set(map.geometry.free.map(c=>c.join(','))),walls=new Set(cells(w,h).map(c=>c.join(',')).filter(k=>!free.has(k)));
  const objects=new Map(s.initial.map(c=>[c.join(','),c]));let paid=0,contacts=0;
  const frames=r.steps.map((f,i)=>{
   if(f.step!==i||!Array.isArray(f.position)||!Number.isFinite(f.heading_yaw)||f.observation_count!==paid+Number(f.observation_granted))throw Error('Invalid historical frame '+i);
   paid=f.observation_count;contacts+=Object.values(f.contacts||{}).reduce((sum,n)=>sum+Number(n),0);
   const changes=s.events.filter(e=>e.step===i);
   for(const e of changes){const k=e.cell.join(',');if(e.action==='remove'||e.action==='move')objects.delete(k);if(e.action==='add')objects.set(k,e.cell);if(e.action==='move'&&e.to)objects.set(e.to.join(','),e.to)}
   const positions=s.positions||[],pedestrians=positions[i]?[{cell:positions[i]}]:[];
   const objects_after=[...objects.values()].map(cell=>({cell}));
   const truth=cells(w,h).map(c=>Number(walls.has(c.join(','))||objects.has(c.join(','))));
   return {step:i,robot_position_after_action_xy:f.position,robot_heading_after_action_rad:f.heading_yaw,executed_action:f.action,observation_granted:f.observation_granted,observation_requested:null,paid_observation_count:f.observation_count,event:{step:i,event_type:i===0?'initial_state':changes.length?'saved_schedule_changes':'no_change_in_saved_schedule',changes},objects_after,pedestrians_xy:pedestrians,memory:null,truth,emergency_safety_scan:f.emergency_scan,emergency_safety_intervention:f.emergency_intervention,selected_action_shield_rejection:{rejected:f.blocked},unwanted_contacts:f.contacts,goal_reached:f.position.join(',')===map.world.goal.join(',')}
  });
  if(paid!==metrics.paidScans||contacts!==metrics.unwantedContacts||frames.at(-1).goal_reached!==entry.success)throw Error('Historical trace outcome mismatch');
  return {replay:{grid:{width:w,height:h},map_family:entry.map.family,start_xy:map.world.start,goal_xy:map.world.goal},frames,walls,metrics,legacy:true}
 }
 async function loadReplay(index,entry,signal){
  if(!root.crypto?.subtle||!root.DecompressionStream)throw Error('Replay needs a modern browser over HTTPS or localhost.');
  const res=await fetchChecked(rawURL(entry),signal),bytes=await res.arrayBuffer();
  if(entry.recovered&&bytes.byteLength!==entry.bytes)throw Error('Recovered replay size mismatch');
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
  if(hash!==entry.sha256)throw Error('Replay SHA-256 verification failed');
  const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  const body=JSON.parse(await new Response(stream).text()),metrics=outcome(body,entry);
  return entry.payload_type==='trace'?historicalTrace(body,entry,metrics,await loadMap(entry,signal)):recordedReplay(body,entry,metrics)
 }
 root.H2Replay={schedules,key,csv,buildIndex,loadIndex,getEntry,decodeMemory,decodeBits,recordedReplay,historicalTrace,loadReplay,originalURL};
})(globalThis);
