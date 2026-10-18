
(()=>{'use strict';
const root=document.getElementById('weather-map'),canvas=root.querySelector('canvas'),ctx=canvas.getContext('2d');
const sequences=[['rain','snow','wind','sun'],['wind','sun','snow','rain'],['sun','wind','sun','wind']];
const labels={rain:'дождь',snow:'снег',wind:'ветер',sun:'солнце',cloudy:'пасмурно',neutral:'без эффекта'};
const specs=[['Dublin',58,73,380,110,'#07542b'],['Helsinki',550,68,485,112,'#06296d'],['Raris',391,219,305,111,'#bd4505'],['Madrid',176,370,431,110,'#a60912']];
const make=(w,h)=>{let c=document.createElement('canvas');c.width=w;c.height=h;return c},rnd=(a,b)=>a+Math.random()*(b-a),TAU=Math.PI*2;
let scene=0,elapsed=0,time=0,last=0,paused=false;
let mode='demo',generation=0,refreshTimer=null,activeRequest=null;
const cityIds=['dublin','helsinki','paris','madrid'];
const modeSelect=root.querySelector('[data-mode]');
const weatherInfo=root.querySelector('[data-weather-info]');
const weatherRows=root.querySelector('[data-weather-rows]');
const liveValues=new Map();

const cities=specs.map(([name,x,y,w,h,color])=>{
 const mask=make(w,h),g=mask.getContext('2d',{willReadFrequently:true});g.font='900 150px Arial';let m=g.measureText(name);g.scale(w/m.width,h/(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent));g.fillStyle=color;g.fillText(name,0,m.actualBoundingBoxAscent);
 const pixels=mask.getContext('2d').getImageData(0,0,w,h).data,top=new Float32Array(w).fill(-1),tiles=[];
 for(let xx=0;xx<w;xx++)for(let yy=0;yy<h;yy++)if(pixels[(yy*w+xx)*4+3]>70){top[xx]=yy;break}
 for(let yy=2;yy<h;yy+=4)for(let xx=2;xx<w;xx+=4)if(pixels[(yy*w+xx)*4+3]>22)tiles.push({x:xx,y:yy});
 const atlas=make(900,Math.ceil(tiles.length/90)*10),a=atlas.getContext('2d');tiles.forEach((p,i)=>{p.ax=i%90*10;p.ay=Math.floor(i/90)*10;a.save();a.beginPath();a.arc(p.ax+5,p.ay+5,3.45,0,TAU);a.clip();a.drawImage(mask,p.ax+5-p.x,p.ay+5-p.y);a.restore()});
 return {name,x,y,w,h,color,mask,top,tiles,atlas,texture:make(w,h),depth:new Float32Array(w),particles:[],hits:[],splashes:[],clouds:[],snowBase:0};
});
function particle(c,e,initial=false){return{x:rnd(-12,c.w+12),y:initial?rnd(-55,c.h+16):-55,v:e==='rain'?rnd(280,450):rnd(30,75),r:rnd(.9,2.5),seed:rnd(0,TAU)}}
function setEffect(c,effect,force=false){
 if(!force&&c.effect===effect)return;
 c.effect=effect;
 c.depth.fill(0);c.snowBase=0;c.hits=[];c.splashes=[];c.particles=Array.from({length:c.effect==='rain'?65:90},()=>particle(c,c.effect,true));c.clouds=Array.from({length:10},(_,j)=>({x:c.w*(j+.3)/10,y:rnd(c.h*.1,c.h*.4),r:rnd(22,37),v:rnd(19,35)}))
}
// Live metrics change visual intensity even when the effect stays the same.
function applyVisualMetrics(c,data){
 const speed=data.wind_speed_kmh;
 c.windScale=typeof speed==='number'&&Number.isFinite(speed)&&speed>=0?
  Math.min(2,Math.max(.5,speed/36)):1;
 const cover=data.cloud_cover_pct;
 const count=typeof cover==='number'&&Number.isFinite(cover)&&cover>=0?
  (cover===0?0:Math.max(1,Math.round(Math.min(100,cover)/5))):10;
 if(c.clouds.length>count)c.clouds.length=count;
 while(c.clouds.length<count){
  const j=c.clouds.length;
  c.clouds.push({x:c.w*(j+.3)/count,y:rnd(c.h*.1,c.h*.4),r:rnd(22,37),v:rnd(19,35)});
 }
}
function describeCanvas(){
 canvas.setAttribute('aria-label',cities.map(c=>c.name+': '+labels[c.effect]).join('; '));
}
function reset(){
 cities.forEach((c,i)=>{c.windScale=1;setEffect(c,sequences[scene][i],true)});
 root.querySelector('[data-status]').textContent=`Демо · Сцена ${scene+1} / 3 · 12 секунд`;
 describeCanvas();
}

function ink(c,x,y){return x>=0&&x<c.w&&y>=0&&y<c.h&&c.top[Math.floor(x)]>=0&&y>=c.top[Math.floor(x)]}
function update(c,dt){const e=c.effect;
 if(e==='rain'||e==='snow')for(const p of c.particles){let old=p.y;p.y+=p.v*dt;p.x+=(e==='snow'?10+Math.sin(time+p.seed)*13:0)*dt;let col=Math.round(p.x);let surface=col>=0&&col<c.w&&c.top[col]>=0?c.top[col]-(e==='snow'?c.depth[col]+c.snowBase:0):Infinity;
 if(old<=surface&&p.y>=surface){if(e==='rain'){c.hits.push({x:p.x,y:surface,t:time});for(let k=0;k<3;k++)c.splashes.push({x:p.x,y:surface,vx:rnd(-55,55),vy:rnd(-80,-25),age:0});}else{for(let k=-5;k<=5;k++){let q=col+k;if(q>=0&&q<c.w&&c.top[q]>=0)c.depth[q]=Math.min(13,c.depth[q]+1.1*Math.exp(-k*k/11))}}Object.assign(p,particle(c,e));}
 if(p.y>c.h+18||p.x>c.w+15)Object.assign(p,particle(c,e));}
 c.hits=c.hits.filter(p=>time-p.t<1.4).slice(-22);c.splashes=c.splashes.filter(p=>p.age<.55);for(const p of c.splashes){p.age+=dt;p.x+=p.vx*dt;p.y+=p.vy*dt;p.vy+=285*dt}
 if(e==='snow')c.snowBase=Math.min(5.5,c.snowBase+dt*.18);
 if(e==='sun'||e==='cloudy')for(const p of c.clouds){p.x+=p.v*dt;if(p.x>c.w+p.r*2)p.x=-p.r*2}
}
function puff(g,x,y,rx,ry,dark=false){g.save();g.translate(x,y);g.scale(rx,ry);let grad=g.createRadialGradient(0,0,0,0,0,1);grad.addColorStop(0,dark?'rgba(55,55,55,.85)':'rgba(255,250,239,.85)');grad.addColorStop(.45,dark?'rgba(55,55,55,.72)':'rgba(255,250,239,.72)');grad.addColorStop(1,dark?'rgba(55,55,55,0)':'rgba(255,250,239,0)');g.fillStyle=grad;g.beginPath();g.arc(0,0,1,0,TAU);g.fill();g.restore()}
function draw(c){ctx.save();ctx.translate(c.x,c.y);const e=c.effect;
 if(e==='neutral'){ctx.drawImage(c.mask,0,0)}
 else if(e==='wind'){for(let y=0;y<c.h;y++){let f=1-y/c.h;let dx=(c.windScale??1)*f*f*(17+11*Math.sin(time*2.4+c.x*.01)+5*Math.sin(time*4+y*.024));ctx.drawImage(c.mask,0,y,c.w,1,dx,y,c.w,1.4)}}
 else if(e==='rain'){for(const p of c.tiles){let dx=0,dy=0;for(const hit of c.hits){let age=time-hit.t,vx=p.x-hit.x,vy=p.y-hit.y,d=Math.hypot(vx,vy),o=d-age*108;if(Math.abs(o)>37)continue;let wave=9.8*Math.cos(o*.13)*Math.exp(-o*o/578-age*1.35);dx+=wave*vx/Math.max(d,1);dy+=wave*vy/Math.max(d,1)}ctx.drawImage(c.atlas,p.ax,p.ay,10,10,p.x-5+dx,p.y-5+dy,10,10)}
 ctx.strokeStyle='rgba(43,129,163,.43)';ctx.lineWidth=1.25;for(const p of c.particles){ctx.beginPath();ctx.moveTo(p.x,p.y-10);ctx.lineTo(p.x,p.y);ctx.stroke()}
 for(const hit of c.hits){let age=time-hit.t;ctx.strokeStyle=`rgba(50,146,176,${.16*(1-age/1.4)})`;ctx.beginPath();ctx.ellipse(hit.x,hit.y,age*65,age*26,0,0,TAU);ctx.stroke()}
 for(const p of c.splashes){ctx.fillStyle=`rgba(45,137,176,${1-p.age/.55})`;ctx.beginPath();ctx.arc(p.x,p.y,1.4,0,TAU);ctx.fill()}}
 else if(e==='snow'){ctx.drawImage(c.mask,0,0);ctx.lineCap='round';for(let pass=0;pass<2;pass++)for(let x=1;x<c.w-1;x+=2){if(c.top[x]<0)continue;let thick=c.snowBase+c.depth[x];if(thick<.13)continue;ctx.lineWidth=Math.max(1.35,thick)+(pass===0?1.25:0);ctx.strokeStyle=pass===0?'#8faebb':'#fff';ctx.beginPath();ctx.moveTo(x-1.1,c.top[x]-thick*.51);ctx.lineTo(x+1.1,c.top[x]-thick*.51);ctx.stroke()}
 for(const p of c.particles){ctx.fillStyle=p.r>1.8?'#fff':'#91b0c0';ctx.strokeStyle='#abc0cb';ctx.lineWidth=.65;ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,TAU);ctx.fill();ctx.stroke()}}
 else if(e==='cloudy'){
 const g=c.texture.getContext('2d');
 g.clearRect(0,0,c.w,c.h);g.fillStyle='#999999';g.fillRect(0,0,c.w,c.h);
 for(const p of c.clouds){
  puff(g,p.x-p.r*.24,p.y,p.r*.72,p.r*.43,true);
  puff(g,p.x,p.y-p.r*.13,p.r*.62,p.r*.53,true);
  puff(g,p.x+p.r*.32,p.y,p.r*.7,p.r*.4,true);
 }
 g.globalCompositeOperation='destination-in';g.drawImage(c.mask,0,0);
 g.globalCompositeOperation='source-over';ctx.drawImage(c.texture,0,0);
 }
 else{let g=c.texture.getContext('2d');g.clearRect(0,0,c.w,c.h);let brightness=.93+Math.sin(time*2.1)*.026+Math.sin(time*4.8+.8)*.012;let fill=g.createLinearGradient(0,0,0,c.h);fill.addColorStop(0,`rgb(255,${Math.round(230*brightness)},88)`);fill.addColorStop(.46,`rgb(255,${Math.round(211*brightness)},17)`);fill.addColorStop(1,'#f6b000');g.fillStyle=fill;g.fillRect(0,0,c.w,c.h);
 g.save();g.beginPath();g.rect(0,0,c.w,c.h*.5);g.clip();for(const p of c.clouds){puff(g,p.x-p.r*.24,p.y,p.r*.72,p.r*.43);puff(g,p.x,p.y-p.r*.13,p.r*.62,p.r*.53);puff(g,p.x+p.r*.32,p.y,p.r*.7,p.r*.4)}g.restore();g.globalCompositeOperation='destination-in';g.drawImage(c.mask,0,0);g.globalCompositeOperation='source-over';ctx.save();ctx.shadowColor='#ffe283';ctx.shadowBlur=12;ctx.drawImage(c.texture,0,0);ctx.restore()}
 ctx.restore();}
function render(now){let dt=last?Math.min((now-last)/1000,.05):0;last=now;if(!paused){time+=dt;if(mode==='demo'){elapsed+=dt;if(elapsed>=12){elapsed-=12;scene=(scene+1)%3;reset()}}cities.forEach(c=>update(c,dt))}ctx.fillStyle='#fff';ctx.fillRect(0,0,1100,578);cities.forEach(draw);root.querySelector('.weather-progress').style.width=elapsed/12*100+'%';requestAnimationFrame(render)}
root.querySelector('[data-pause]').onclick=()=>{paused=!paused;root.querySelector('[data-pause]').textContent=paused?'Продолжить':'Пауза'};
root.querySelector('[data-next]').onclick=()=>{if(mode!=='demo')return;scene=(scene+1)%3;elapsed=0;reset()};

function formatTime(value){
 const date=new Date(value);
 return value&&Number.isFinite(date.getTime())?date.toLocaleString('ru-RU'):'нет данных';
}
function metric(value,unit){
 return typeof value==='number'&&Number.isFinite(value)?value.toLocaleString('ru-RU')+' '+unit:'нет данных';
}
function showExplanations(connectionFailed){
 const container=root.querySelector('[data-weather-explanations]');
 container.replaceChildren();
 cities.forEach((city,i)=>{
  const data=liveValues.get(cityIds[i]);
  const section=document.createElement('section');
  const heading=document.createElement('h3');
  heading.textContent=city.name+' · '+labels[city.effect];
  section.append(heading);
  const add=text=>{const p=document.createElement('p');p.textContent=text;section.append(p);};
  if(connectionFailed||data?.status==='stale')add('Последние доступные данные: объяснение относится к погоде на '+formatTime(data?.data_time)+'.');
  const interval=data?.precipitation_interval_seconds;
  const period=typeof interval==='number'&&Number.isFinite(interval)&&interval>0?
   'за предыдущие '+metric(interval/60,'мин'):'интервал неизвестен';
  add('Ветер: '+metric(typeof data?.wind_speed_kmh==='number'?Math.round(data.wind_speed_kmh/3.6*10)/10:null,'м/с')+' ('+metric(data?.wind_speed_kmh,'км/ч')+')'+'; направление: '+metric(data?.wind_direction_deg,'°')+'. Облачность: '+metric(data?.cloud_cover_pct,'%')+'.');
  add('Осадки ('+period+'): всего '+metric(data?.precipitation_mm,'мм')+
   '; дождь '+metric(data?.rain_mm,'мм')+'; ливни '+metric(data?.showers_mm,'мм')+'; снег '+metric(data?.snowfall_cm,'см')+'.');
  add('Код погоды: '+metric(data?.weather_code,'').trim()+'. Время суток: '+(data?.is_day===1?'день':data?.is_day===0?'ночь':'нет данных')+'.');
  add(typeof data?.effect_reason==='string'&&data.effect_reason?
   data.effect_reason:data?.data_time?'Причина выбора не получена. Обновите сервер и страницу.':'Погодные данные недоступны. Показана обычная надпись.');
  container.append(section);
 });
}
function showWeather(connectionFailed=false){
 showExplanations(connectionFailed);
 weatherRows.replaceChildren();
 cities.forEach((city,i)=>{
  const data=liveValues.get(cityIds[i]);
  const row=document.createElement('li');
  const status=connectionFailed?(data?.data_time?'связь потеряна, последние данные':'нет данных'):
   ({fresh:'актуальные',stale:'устаревшие',unavailable:'нет данных'}[data?.status]||'нет данных');
  const temp=typeof data?.temperature_c==='number'&&Number.isFinite(data.temperature_c)?data.temperature_c+' °C':'—';
  row.textContent=`${city.name}: ${labels[city.effect]} · ${temp} · ${status} · погода на ${formatTime(data?.data_time)}`;
  if(data?.missing_fields?.length)row.textContent+=' · часть показателей отсутствует';
  weatherRows.append(row);
 });
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
  setEffect(city,data.effect);
  applyVisualMetrics(city,data);
 });
 describeCanvas();
 showWeather();
 const degraded=[...liveValues.values()].some(c=>c.status!=='fresh');
 root.querySelector('[data-status]').textContent=degraded?
  'Реальная погода · часть данных недоступна или устарела':
  'Реальная погода · обновление раз в 10 минут';
 return degraded?60000:600000;
}
async function refreshWeather(version){
 const controller=new AbortController();
 activeRequest=controller;
 const timeout=setTimeout(()=>controller.abort(),30000);
 let delay=60000;
 try{
  const response=await fetch('/api/weather?map=legacy',{signal:controller.signal,cache:'no-store'});
  if(!response.ok)throw new Error('Weather HTTP '+response.status);
  const data=await response.json();
  if(mode!=='live'||version!==generation)return;
  delay=applyWeather(data);
 }catch(error){
  if(mode!=='live'||version!==generation)return;
  root.querySelector('[data-status]').textContent='Не удалось обновить погоду · повтор через минуту';
  showWeather(true);
 }finally{
  clearTimeout(timeout);
  if(activeRequest===controller)activeRequest=null;
  if(mode==='live'&&version===generation)refreshTimer=setTimeout(()=>refreshWeather(version),delay);
 }
}
modeSelect.addEventListener('change',()=>{
 mode=modeSelect.value;
 generation++;
 clearTimeout(refreshTimer);
 activeRequest?.abort();
 root.querySelector('[data-next]').disabled=mode==='live';
 root.querySelector('.weather-track').hidden=mode==='live';
 weatherInfo.hidden=mode!=='live';
 if(mode==='demo'){
  scene=0;elapsed=0;reset();
 }else{
  liveValues.clear();
  cities.forEach(c=>setEffect(c,'neutral'));
  describeCanvas();showWeather();
  root.querySelector('[data-status]').textContent='Загрузка реальной погоды…';
  refreshWeather(generation);
 }
});
if(location.protocol==='file:'){
 modeSelect.querySelector('[value="live"]').disabled=true;
 root.querySelector('[data-local-hint]').hidden=false;
}
reset();requestAnimationFrame(render);
})();
