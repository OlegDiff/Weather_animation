
(()=>{'use strict';
const root=document.getElementById('weather-map'),canvas=root.querySelector('canvas'),ctx=canvas.getContext('2d');
function fitMapToScreen(){
 const bodyStyle=getComputedStyle(document.body);
 const controls=root.querySelector('.map-controls'),source=root.querySelector('.data-source');
 const sourceStyle=getComputedStyle(source);
 const viewportHeight=window.visualViewport?.height??window.innerHeight;
 if(window.matchMedia('(orientation: landscape) and (hover: none) and (pointer: coarse)').matches){
  root.style.setProperty('--map-display-width',viewportHeight*canvas.width/canvas.height+'px');
  return;
 }
 const availableHeight=Math.max(1,viewportHeight-parseFloat(bodyStyle.paddingTop)-parseFloat(bodyStyle.paddingBottom)
  -controls.getBoundingClientRect().height-source.getBoundingClientRect().height
  -parseFloat(sourceStyle.marginTop)-parseFloat(sourceStyle.marginBottom));
 const width=Math.min(root.clientWidth,availableHeight*canvas.width/canvas.height);
 root.style.setProperty('--map-display-width',width+'px');
}
window.addEventListener('resize',fitMapToScreen);
window.visualViewport?.addEventListener('resize',fitMapToScreen);
const layoutObserver=new ResizeObserver(fitMapToScreen);
layoutObserver.observe(root.querySelector('.map-controls'));
layoutObserver.observe(root.querySelector('.data-source'));
fitMapToScreen();
// Synthetic geography-based stages; thresholds are visual settings, not forecasts.
const STAGE_SECONDS=6, FADE_SECONDS=3, SPREAD_SECONDS=0;
const stageNames=['Snow across Europe','Snow retreats north','More sunshine','Rain and clouds','Snow returns to the north'];
function demoEffect(city,stage){
 let hash=0;for(const char of city.id)hash=(hash*31+char.charCodeAt(0))>>>0;
 const patch=(hash%1000)/1000,lat=city.latitude;
 if(stage===0){
  if(lat>=51)return 'snow';
  if(lat>=45)return patch<.52?'rain':'cloudy';
  return patch<.42?'cloudy':'sun';
 }
 if(stage===1){
  if(lat>=57)return 'snow';
  return patch<.55?'sun':patch<.78?'rain':'cloudy';
 }
 if(stage===2)return patch<.72?'sun':patch<.86?'cloudy':'rain';
 if(stage===3)return patch<.20?'sun':patch<.62?'rain':'cloudy';
 if(lat>=58)return 'snow';
 return patch<.15?'sun':patch<.58?'rain':'cloudy';
}
const sequences=stageNames.map((_,stage)=>window.WEATHER_MAP.cities.map(c=>demoEffect(c,stage)));
const labels={rain:'rain',snow:'snow',wind:'wind',sun:'sunny',cloudy:'cloudy',neutral:'no active effect'};
const map=window.WEATHER_MAP;
const specs=map.cities.map(c=>[c.name,Math.round(c.x*1600/1672),Math.round(c.y*900/941),Math.round(c.w*1600/1672),Math.round(c.h*900/941),'#151515']);

const make=(w,h)=>{let c=document.createElement('canvas');c.width=w;c.height=h;return c},rnd=(a,b)=>a+Math.random()*(b-a),TAU=Math.PI*2;
let scene=0,elapsed=0,time=0,last=0,paused=false;
let mode='demo',generation=0,refreshTimer=null,activeRequest=null;
const cityIds=map.cities.map(c=>c.id);
const modeControls=root.querySelectorAll('[data-mode]');
const liveValues=new Map();
const windLegend=root.querySelector('.legend-wind'),windLegendMask=make(48,36);
const windLegendInk=windLegendMask.getContext('2d');
windLegendInk.font='bold 26px Arial';windLegendInk.fillStyle='#555';windLegendInk.fillText('Aa',3,30);

const cities=specs.map(([name,x,y,w,h,color])=>{
 const mask=make(w,h),g=mask.getContext('2d',{willReadFrequently:true});g.font=(h<22?'400':'900')+' 150px Arial';let m=g.measureText(name);g.scale(w/m.width,h/(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent));g.fillStyle=color;g.fillText(name,0,m.actualBoundingBoxAscent);
 // The lower cloud edge is halfway down the lowercase x-height.
 const cloudBottom=h*(m.actualBoundingBoxAscent-g.measureText('x').actualBoundingBoxAscent/2)/(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent);
 if(name==='Santiago de Compostela'){
  g.setTransform(1,0,0,1,0,0);g.clearRect(0,0,w,h);
  ['Santiago','de Compostela'].forEach((line,index)=>{
   g.save();const size=g.measureText(line);
   g.scale(w/size.width,(h/2)/(size.actualBoundingBoxAscent+size.actualBoundingBoxDescent));
   g.fillText(line,0,size.actualBoundingBoxAscent+index*(size.actualBoundingBoxAscent+size.actualBoundingBoxDescent));g.restore();
  });
 }

 const pixels=mask.getContext('2d').getImageData(0,0,w,h).data,top=new Float32Array(w).fill(-1),tiles=[];
 for(let xx=0;xx<w;xx++)for(let yy=0;yy<h;yy++)if(pixels[(yy*w+xx)*4+3]>70){top[xx]=yy;break}
 for(let yy=2;yy<h;yy+=4)for(let xx=2;xx<w;xx+=4)if(pixels[(yy*w+xx)*4+3]>22)tiles.push({x:xx,y:yy});
 const atlas=make(900,Math.ceil(tiles.length/90)*10),a=atlas.getContext('2d');tiles.forEach((p,i)=>{p.ax=i%90*10;p.ay=Math.floor(i/90)*10;a.save();a.beginPath();a.arc(p.ax+5,p.ay+5,3.45,0,TAU);a.clip();a.drawImage(mask,p.ax+5-p.x,p.ay+5-p.y);a.restore()});
 return {name,x,y,w,h,color,cloudBottom,mask,top,tiles,atlas,texture:make(w,h),depth:new Float32Array(w),particles:[],hits:[],splashes:[],clouds:[],snowBase:0,scale:h/110};
});
function particle(c,e,initial=false){return{x:rnd(-12,c.w+12),y:initial?rnd(-12,c.h+8):-12,v:(e==='rain'?rnd(280,450):rnd(30,75))*c.scale,r:rnd(.9,2.5)*Math.max(.45,c.scale),seed:rnd(0,TAU)}}
function setEffect(c,effect,force=false){
 if(!force&&c.effect===effect)return;
 c.effect=effect;
 c.depth.fill(0);c.snowBase=0;c.hits=[];c.splashes=[];c.particles=Array.from({length:c.effect==='rain'?Math.max(6,Math.round(c.w/12)):Math.max(8,Math.round(c.w/10))},()=>particle(c,c.effect,true));c.clouds=Array.from({length:Math.min(10,Math.ceil(c.w/32))},(_,j)=>({x:c.w*(j+.3)/Math.min(10,Math.ceil(c.w/32)),y:rnd(c.h*.1,c.cloudBottom*.85),r:rnd(16,26)*c.scale,v:rnd(19,35)*c.scale}))
}
// Live metrics change visual intensity even when the effect stays the same.
function applyVisualMetrics(c,data){
 const speed=data.wind_speed_kmh;
 c.windScale=typeof speed==='number'&&Number.isFinite(speed)&&speed>=0?
  c.scale*Math.min(2,Math.max(.5,speed/36)):c.scale;
 const cover=data.cloud_cover_pct;
 const count=typeof cover==='number'&&Number.isFinite(cover)&&cover>=0?
  (cover===0?0:Math.max(1,Math.round(Math.min(100,cover)/5*Math.min(1,c.w/200)))):10;
 if(c.clouds.length>count)c.clouds.length=count;
 while(c.clouds.length<count){
  const j=c.clouds.length;
  c.clouds.push({x:c.w*(j+.3)/count,y:rnd(c.h*.1,c.cloudBottom*.85),r:rnd(16,26)*c.scale,v:rnd(19,35)*c.scale});
 }
}
function describeCanvas(){
 canvas.setAttribute('aria-label',cities.map(c=>c.name+': '+labels[c.effect]+(c.windActive&&c.effect!=='wind'?' + wind':'')).join('; '));
}
function reset(immediate=true){
 cities.forEach((c,i)=>{
  c.windActive=false;
  c.windScale=c.scale;
  if(immediate){c.transition=null;c.pending=null;setEffect(c,sequences[scene][i],true);}
  else{
   const latitude=map.cities[i].latitude;
   // Thaw travels south to north; returning snow travels north to south.
   const north=Math.max(0,Math.min(1,(latitude-36)/25));
   c.pending={effect:sequences[scene][i],at:time+SPREAD_SECONDS*(scene===1?north:1-north)};
  }
 });
 root.querySelector('[data-status]').textContent=`DEMO: ${stageNames[scene]}`;
 describeCanvas();
}
function advanceDemo(){scene=(scene+1)%sequences.length;elapsed=0;reset(false);}
function updateCity(c,dt){
 if(c.pending&&time>=c.pending.at){
  const effect=c.pending.effect;c.pending=null;
  if(effect!==c.effect){
   const previous={...c,depth:c.depth.slice(),texture:make(c.w,c.h),transition:null,pending:null};
   setEffect(c,effect);
   c.transition={previous,start:time};
   describeCanvas();
  }
 }
 update(c,dt);
 if(c.transition){
  update(c.transition.previous,dt);
  if(time-c.transition.start>=FADE_SECONDS)c.transition=null;
 }
}
function drawCity(c){
 if(!c.transition){drawLayer(c);return;}
 const t=Math.max(0,Math.min(1,(time-c.transition.start)/FADE_SECONDS));
 const blend=t*t*(3-2*t);
 ctx.save();ctx.globalAlpha=1-blend;drawLayer(c.transition.previous);
 ctx.globalAlpha=blend;drawLayer(c);ctx.restore();
}

function windOffset(c,y){
 const f=1-y/c.h;
 return (c.windScale??1)*f*f*(17+11*Math.sin(time*2.4+c.x*.01)+5*Math.sin(time*4+y*.024));
}
function drawLayer(c){
 if(!c.windActive||c.effect==='wind'){draw(c);return;}
 // Render the complete weather layer first, then bend it without losing its colours or particles.
 const pad=24,w=c.w+pad*2,h=c.h+pad*2;
 const layer=c.windTexture||(c.windTexture=make(w,h)),g=layer.getContext('2d');
 g.clearRect(0,0,w,h);g.save();g.translate(pad-c.x,pad-c.y);draw(c,g);g.restore();
 for(let y=0;y<h;y++){
  const dx=windOffset(c,Math.max(0,Math.min(c.h,y-pad)));
  ctx.drawImage(layer,0,y,w,1,c.x-pad+dx,c.y-pad+y,w,1.4);
 }
}
function drawWindLegend(){
 const g=windLegend.getContext('2d');g.clearRect(0,0,48,36);
 const sample={h:36,windScale:.3,x:0};
 for(let y=0;y<36;y++)g.drawImage(windLegendMask,0,y,48,1,windOffset(sample,y),y,48,1.4);
}

function ink(c,x,y){return x>=0&&x<c.w&&y>=0&&y<c.h&&c.top[Math.floor(x)]>=0&&y>=c.top[Math.floor(x)]}
function update(c,dt){const e=c.effect;
 if(e==='rain'||e==='snow')for(const p of c.particles){let old=p.y;p.y+=p.v*dt;p.x+=(e==='snow'?10+Math.sin(time+p.seed)*13:0)*dt;let col=Math.round(p.x);let surface=col>=0&&col<c.w&&c.top[col]>=0?c.top[col]-(e==='snow'?c.depth[col]+c.snowBase:0):Infinity;
 if(old<=surface&&p.y>=surface){if(e==='rain'){c.hits.push({x:p.x,y:surface,t:time});for(let k=0;k<3;k++)c.splashes.push({x:p.x,y:surface,vx:rnd(-55,55),vy:rnd(-80,-25),age:0});}else{for(let k=-5;k<=5;k++){let q=col+k;if(q>=0&&q<c.w&&c.top[q]>=0)c.depth[q]=Math.min(13*c.scale,c.depth[q]+1.1*c.scale*Math.exp(-k*k/11))}}Object.assign(p,particle(c,e));}
 if(p.y>c.h+18||p.x>c.w+15)Object.assign(p,particle(c,e));}
 c.hits=c.hits.filter(p=>time-p.t<1.4).slice(-22);c.splashes=c.splashes.filter(p=>p.age<.55);for(const p of c.splashes){p.age+=dt;p.x+=p.vx*dt;p.y+=p.vy*dt;p.vy+=285*dt}
 if(e==='snow')c.snowBase=Math.min(5.5*c.scale,c.snowBase+dt*.18*c.scale);
 if(e==='sun'||e==='cloudy')for(const p of c.clouds){p.x+=p.v*dt;if(p.x>c.w+p.r*2)p.x=-p.r*2}
}
function puff(g,x,y,rx,ry){g.save();g.translate(x,y);g.scale(rx,ry);let grad=g.createRadialGradient(0,0,0,0,0,1);grad.addColorStop(0,'rgba(255,255,255,1)');grad.addColorStop(.65,'rgba(255,255,255,.95)');grad.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=grad;g.beginPath();g.arc(0,0,1,0,TAU);g.fill();g.restore()}
function draw(c,output=ctx){const gctx=output;gctx.save();gctx.translate(c.x,c.y);const e=c.effect;
 if(e==='neutral'){gctx.drawImage(c.mask,0,0)}
 else if(e==='wind'){for(let y=0;y<c.h;y++){let dx=windOffset(c,y);gctx.drawImage(c.mask,0,y,c.w,1,dx,y,c.w,1.4)}}
 else if(e==='rain'){
 const g=c.texture.getContext('2d');
 g.clearRect(0,0,c.w,c.h);g.fillStyle='#4263A4';g.fillRect(0,0,c.w,c.h);
 g.globalCompositeOperation='destination-in';g.drawImage(c.mask,0,0);
 g.globalCompositeOperation='source-over';
 for(let y=0;y<c.h;y+=2){
  let dx=0;
  for(const hit of c.hits){let age=time-hit.t;dx+=Math.sin(y*.4-age*8)*Math.exp(-age*3)*2*c.scale;}
  gctx.drawImage(c.texture,0,y,c.w,Math.min(2,c.h-y),dx,y,c.w,Math.min(2,c.h-y));
 }
 gctx.strokeStyle='rgba(43,129,163,.43)';gctx.lineWidth=1.25;for(const p of c.particles){gctx.beginPath();gctx.moveTo(p.x,p.y-10);gctx.lineTo(p.x,p.y);gctx.stroke()}
 for(const hit of c.hits){let age=time-hit.t;gctx.strokeStyle=`rgba(50,146,176,${.16*(1-age/1.4)})`;gctx.beginPath();gctx.ellipse(hit.x,hit.y,age*65,age*26,0,0,TAU);gctx.stroke()}
 for(const p of c.splashes){gctx.fillStyle=`rgba(45,137,176,${1-p.age/.55})`;gctx.beginPath();gctx.arc(p.x,p.y,1.4,0,TAU);gctx.fill()}}
 else if(e==='snow'){
 const g=c.texture.getContext('2d');
 g.clearRect(0,0,c.w,c.h);g.fillStyle='#003366';g.fillRect(0,0,c.w,c.h);
 g.globalCompositeOperation='destination-in';g.drawImage(c.mask,0,0);
 g.globalCompositeOperation='source-over';gctx.drawImage(c.texture,0,0);
 gctx.lineCap='round';for(let pass=0;pass<2;pass++)for(let x=1;x<c.w-1;x+=2){if(c.top[x]<0)continue;let thick=c.snowBase+c.depth[x];if(thick<.13)continue;gctx.lineWidth=Math.max(1.35,thick)+(pass===0?1.25:0);gctx.strokeStyle=pass===0?'#8faebb':'#fff';gctx.beginPath();gctx.moveTo(x-1.1,c.top[x]-thick*.51);gctx.lineTo(x+1.1,c.top[x]-thick*.51);gctx.stroke()}
 for(const p of c.particles){gctx.fillStyle='#fff';gctx.strokeStyle='#fff';gctx.lineWidth=.65;gctx.beginPath();gctx.arc(p.x,p.y,p.r,0,TAU);gctx.fill();gctx.stroke()}}
 else if(e==='cloudy'){
 const g=c.texture.getContext('2d');
 g.clearRect(0,0,c.w,c.h);g.fillStyle='#999999';g.fillRect(0,0,c.w,c.h);
 g.save();g.beginPath();g.rect(0,0,c.w,c.cloudBottom);g.clip();
 for(const p of c.clouds){
  puff(g,p.x-p.r*.24,p.y,p.r*.72,p.r*.43);
  puff(g,p.x,p.y-p.r*.13,p.r*.62,p.r*.53);
  puff(g,p.x+p.r*.32,p.y,p.r*.7,p.r*.4);
 }
 g.restore();g.globalCompositeOperation='destination-in';g.drawImage(c.mask,0,0);
 g.globalCompositeOperation='source-over';gctx.drawImage(c.texture,0,0);
 }
 else{let g=c.texture.getContext('2d');g.clearRect(0,0,c.w,c.h);let brightness=.93+Math.sin(time*2.1)*.026+Math.sin(time*4.8+.8)*.012;let fill=g.createLinearGradient(0,0,0,c.h);fill.addColorStop(0,`rgb(255,${Math.round(230*brightness)},88)`);fill.addColorStop(.46,`rgb(255,${Math.round(211*brightness)},17)`);fill.addColorStop(1,'#f6b000');g.fillStyle=fill;g.fillRect(0,0,c.w,c.h);
 g.save();g.beginPath();g.rect(0,0,c.w,c.cloudBottom);g.clip();for(const p of c.clouds){puff(g,p.x-p.r*.24,p.y,p.r*.72,p.r*.43);puff(g,p.x,p.y-p.r*.13,p.r*.62,p.r*.53);puff(g,p.x+p.r*.32,p.y,p.r*.7,p.r*.4)}g.restore();g.globalCompositeOperation='destination-in';g.drawImage(c.mask,0,0);g.globalCompositeOperation='source-over';gctx.save();gctx.shadowColor='#ffe283';gctx.shadowBlur=12*c.scale;gctx.drawImage(c.texture,0,0);gctx.restore()}
 gctx.restore();}
function render(now){
 const dt=last?Math.min((now-last)/1000,.05):0;last=now;
 if(!paused){
  time+=dt;
  if(mode==='demo'){elapsed+=dt;if(elapsed>=STAGE_SECONDS)advanceDemo();}
  cities.forEach(c=>updateCity(c,dt));
 }
 ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);cities.forEach(drawCity);drawWindLegend();

 requestAnimationFrame(render);
}
function showWeather(connectionFailed=false){
 if(root.dataset.weatherUrl){
  const maxAge=Number(root.dataset.maxAgeSeconds)*1000;
  for(const data of liveValues.values()){
   if(data.status==='fresh'&&Date.now()-Date.parse(data.data_time)>maxAge)data.status='stale';
  }
 }
 if(connectionFailed)root.querySelector('[data-status]').textContent='Weather update failed. Showing the last available data; retrying in one minute.';
}

function applyWeather(payload){
 if(!payload||payload.mode!=='live'||!Array.isArray(payload.cities))throw new Error('Invalid weather response');
 const incoming=new Map(payload.cities.filter(c=>c&&typeof c.id==='string').map(c=>[c.id,c]));
 cities.forEach((city,i)=>{
  const value=incoming.get(cityIds[i]);
  const valid=value&&['fresh','stale'].includes(value.status)&&
   typeof value.data_time==='string'&&Number.isFinite(Date.parse(value.data_time))&&
   Object.prototype.hasOwnProperty.call(labels,value.effect);
  const data=valid?value:{status:'unavailable',effect:'neutral',data_time:null};
  liveValues.set(cityIds[i],data);
  const effects=Array.isArray(data.effects)?data.effects:[data.effect];
  const base=effects.find(effect=>['rain','snow','cloudy'].includes(effect));
  const combined=effects.includes('wind')&&Boolean(base);
  city.windActive=combined;
  setEffect(city,combined?base:data.effect);
  applyVisualMetrics(city,data);
 });
 describeCanvas();
 showWeather();
 const degraded=[...liveValues.values()].some(c=>c.status!=='fresh');
 root.querySelector('[data-status]').textContent=degraded?
  'REAL: some weather data is unavailable or outdated':
  'REAL: current weather data';
 return root.dataset.weatherUrl?60000:(degraded?60000:600000);
}
async function refreshWeather(version){
 const controller=new AbortController();
 activeRequest=controller;
 const timeout=setTimeout(()=>controller.abort(),45000);
 let delay=60000;
 try{
  const response=await fetch(root.dataset.weatherUrl||'api/weather?map=europe',{signal:controller.signal,cache:'no-store'});
  if(!response.ok)throw new Error('Weather HTTP '+response.status);
  const data=await response.json();
  if(mode!=='live'||version!==generation)return;
  delay=applyWeather(data);
 }catch(error){
  if(mode!=='live'||version!==generation)return;

  showWeather(true);
 }finally{
  clearTimeout(timeout);
  if(activeRequest===controller)activeRequest=null;
  if(mode==='live'&&version===generation)refreshTimer=setTimeout(()=>refreshWeather(version),delay);
 }
}
function changeMode(nextMode){
 mode=nextMode;
 modeControls.forEach(control=>{control.checked=control.value===mode});
 generation++;
 clearTimeout(refreshTimer);
 activeRequest?.abort();
 if(mode==='demo'){
  scene=0;elapsed=0;reset();
 }else{
  liveValues.clear();
  cities.forEach(c=>{c.pending=null;c.transition=null;c.windActive=false;setEffect(c,'neutral')});
  describeCanvas();showWeather();
  root.querySelector('[data-status]').textContent='Loading real weather...';
  refreshWeather(generation);
 }
}
modeControls.forEach(control=>control.addEventListener('change',()=>changeMode(control.value)));
if(location.protocol==='file:'){
 const realControl=root.querySelector('[data-mode][value="live"]');
 realControl.disabled=true;
 realControl.closest('label').title='REAL requires an HTTP server';
}
canvas.addEventListener('pointermove',event=>{
 const box=canvas.getBoundingClientRect(),x=(event.clientX-box.left)*canvas.width/box.width,y=(event.clientY-box.top)*canvas.height/box.height;
 const city=cities.find(c=>x>=c.x&&x<=c.x+c.w&&y>=c.y&&y<=c.y+c.h);
 canvas.title=city?city.name+' · '+labels[city.effect]:'';
});
reset();requestAnimationFrame(render);
if(new URLSearchParams(location.search).get('mode')==='live'&&location.protocol!=='file:'){
 changeMode('live');
}
})();
