'use strict';

const $ = id => document.getElementById(id);
const N = 128;
const colors = {text:'#e7edf5', muted:'#99aac0', grid:'#253449', ps:'#7baaff', pl:'#56dfce', amber:'#ffca7b'};
const state = {data:null, baseline:null, ps:'double', difference:false, fit:false, selected:[107,20], chirp:0, phase:0, timer:null, arch:'e14', sessions:new Map(), serial:0, busy:false};
const format = (n, digits=2) => n == null || !Number.isFinite(n) ? '—' : n.toLocaleString('en-US', {minimumFractionDigits:digits,maximumFractionDigits:digits});
const complex = value => `${format(value[0],3)} ${value[1] < 0 ? '−' : '+'} ${format(Math.abs(value[1]),3)}j`;
const magnitude = value => Math.hypot(value[0],value[1]);
const db = (value, peak) => Math.max(-70,Math.min(0,20*Math.log10(Math.max(value,1e-15)/Math.max(peak,1e-15))));

function message(text, error=false) { $('message').textContent=text; $('message').classList.toggle('error',error); }
async function api(path, values) {
  const response = await fetch(path, values === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});
  const body = await response.json();
  if(!response.ok) throw new Error(body.error || '데이터를 불러오지 못했습니다.');
  return body;
}
function busy(value) {
  state.busy=value;
  for(const id of ['simulate','reload','import-submit','session']) $(id).disabled=value;
  $('simulate').textContent=value ? '처리 중…' : '시뮬레이션 실행';
}
function activate(data, key) {
  stopPlayback(); state.data=data; state.phase=0; state.ps='double'; state.chirp=0;
  const peak=data.peaks.pl; state.selected=[peak.doppler_bin,peak.range_bin];
  state.sessions.set(key,data);
  if(![...$('session').options].some(o=>o.value===key)) {
    const option=document.createElement('option'); option.value=key; option.textContent=data.name; $('session').append(option);
  }
  // Keep the default record plus the latest seven user frames in memory.
  while(state.sessions.size>8) {
    const remove=[...state.sessions.keys()].find(k=>k!=='recording' && k!==key);
    state.sessions.delete(remove); [...$('session').options].find(o=>o.value===remove)?.remove();
  }
  $('session').value=key; $('ps-variant').replaceChildren();
  for(const variant of ['double','float_neon']) if(data.spectra[variant]) {
    const option=document.createElement('option');option.value=variant;option.textContent=variant==='double'?'PS double':'PS NEON';$('ps-variant').append(option);
  }
  $('frame-title').textContent=data.name;
  $('source-badge').textContent={recording:'기록 재생',simulation:'소프트웨어 시뮬레이션',import:'사용자 CSV'}[data.kind];
  $('source-note').textContent=data.kind==='recording' ? 'RadarSimPy 입력 · 검증된 저장 결과가 있으면 SHA-256 확인 후 사용합니다.' : data.kind==='simulation' ? (data.engine==='radarsimpy'?'프로젝트 RadarSimPy를 직접 실행한 입력입니다. PL은 Q15 소프트웨어 모델입니다.':'PC에서 계산한 합성 신호입니다. PL 결과도 Q15 소프트웨어 모델입니다.') : '사용자가 제공한 결과입니다. 입력·정규화와 보드 출처를 별도로 확인하세요.';
  $('normalization').textContent=data.normalization+' · 입력 I/Q는 Q15 입력 단위';
  $('chirp').value=0; $('export').disabled=false;
  $('sources').replaceChildren();
  for(const source of [...data.sources,...Object.values(data.labels)]) { const li=document.createElement('li');li.textContent=source;$('sources').append(li); }
  if(data.fixture_sha256) {const li=document.createElement('li');li.textContent='입력 SHA-256: '+data.fixture_sha256;$('sources').append(li);}
  renderSignal(); renderFlow();
  message(data.kind==='simulation' ? `${data.engine==='radarsimpy'?'RadarSimPy 입력 생성':'합성 신호 계산'} 완료 · 보드 측정은 수행하지 않았습니다. 성능 탭은 기존 E14 기록입니다.` : data.kind==='import' ? 'CSV 불러오기 완료 · 보드 성능 기록은 가져온 파일에 적용되지 않습니다.' : '기준 프레임 준비 완료 · 히트맵을 클릭하거나 bin 번호를 입력해 두 결과를 비교하세요.');
}

function canvasContext(id) {
  const canvas=$(id), width=canvas.clientWidth, height=canvas.clientHeight;
  if(width<10 || height<10) return null;
  const scale=window.devicePixelRatio||1;
  canvas.width=Math.round(width*scale);canvas.height=Math.round(height*scale);
  const ctx=canvas.getContext('2d');ctx.scale(scale,scale);ctx.clearRect(0,0,width,height);
  ctx.font='11px "Segoe UI", "Malgun Gothic", sans-serif';ctx.lineWidth=1;
  return {canvas,ctx,width,height};
}
function bounds() {
  if(!state.fit) return {r0:0,r1:N,d0:0,d1:N};
  const p=state.data.peaks.pl, sd=p.shifted_doppler_bin;
  return {r0:Math.max(0,p.range_bin-12),r1:Math.min(N,p.range_bin+13),d0:Math.max(0,sd-18),d1:Math.min(N,sd+19)};
}
const palette=[[13,24,43],[33,70,115],[48,127,162],[67,198,189],[229,234,160],[255,187,91]];
function heatColor(value) {
  const position=Math.max(0,Math.min(1,(value+70)/70))*(palette.length-1);
  const i=Math.min(palette.length-2,Math.floor(position)), t=position-i;
  return palette[i].map((v,k)=>Math.round(v+(palette[i+1][k]-v)*t));
}
function heatmap(id, values, referencePeak) {
  const drawing=canvasContext(id);if(!drawing) return;
  const {ctx,width,height,canvas}=drawing, area={x:51,y:17,w:width-65,h:height-64};
  const b=bounds(), nx=b.r1-b.r0, ny=b.d1-b.d0;
  const imageCanvas=document.createElement('canvas');imageCanvas.width=nx;imageCanvas.height=ny;
  const imageCtx=imageCanvas.getContext('2d'), image=imageCtx.createImageData(nx,ny);
  for(let y=0;y<ny;y++) for(let x=0;x<nx;x++) {
    const sd=b.d1-1-y, d=(sd+64)%N, value=values[d*N+b.r0+x];
    const rgb=heatColor(db(magnitude(value),referencePeak)), offset=(y*nx+x)*4;
    image.data.set([...rgb,255],offset);
  }
  imageCtx.putImageData(image,0,0);ctx.imageSmoothingEnabled=false;ctx.drawImage(imageCanvas,area.x,area.y,area.w,area.h);
  const ranges=state.data.axes.range_m, velocities=state.data.axes.velocity_mps;
  const dx=ranges[1]-ranges[0],dy=velocities[1]-velocities[0];
  const xCoord=r=>area.x+(r-b.r0+.5)/nx*area.w;
  const yCoord=d=>area.y+(b.d1-d-.5)/ny*area.h;
  ctx.fillStyle=colors.muted;ctx.textAlign='center';
  for(let k=0;k<=4;k++) {
    const r=b.r0+(nx-1)*k/4,x=xCoord(r);ctx.fillText(format(r*dx,0),x,area.y+area.h+19);
  }
  ctx.fillText('거리 (m)',area.x+area.w/2,height-4);ctx.textAlign='right';
  for(let k=0;k<=4;k++) {
    const sd=b.d0+(ny-1)*k/4,y=yCoord(sd);ctx.fillText(format(velocities[b.d0]+(sd-b.d0)*dy,1),area.x-8,y+4);
  }
  ctx.save();ctx.translate(12,area.y+area.h/2);ctx.rotate(-Math.PI/2);ctx.textAlign='center';ctx.fillText('속도 (m/s)',0,0);ctx.restore();
  ctx.save();ctx.beginPath();ctx.rect(area.x,area.y,area.w,area.h);ctx.clip();
  if(state.data.truth) {
    const r=state.data.truth.range_m/dx,d=(state.data.truth.velocity_mps-velocities[0])/dy;
    const x=xCoord(r),y=yCoord(d);ctx.strokeStyle=colors.amber;ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(x-7,y);ctx.lineTo(x+7,y);ctx.moveTo(x,y-7);ctx.lineTo(x,y+7);ctx.stroke();
  }
  const [d,r]=state.selected, sd=(d+64)%N, x=xCoord(r), y=yCoord(sd);
  ctx.strokeStyle=colors.text;ctx.lineWidth=1;ctx.setLineDash([3,4]);ctx.beginPath();ctx.moveTo(x,area.y);ctx.lineTo(x,area.y+area.h);ctx.moveTo(area.x,y);ctx.lineTo(area.x+area.w,y);ctx.stroke();
  ctx.setLineDash([]);ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(x,y-6);ctx.lineTo(x+6,y);ctx.lineTo(x,y+6);ctx.lineTo(x-6,y);ctx.closePath();ctx.stroke();ctx.restore();
  canvas._plot={area,b};
}

function lineChart(id, series, xMin, xMax, yMin, yMax, xTitle, yTitle) {
  const drawing=canvasContext(id);if(!drawing) return;
  const {ctx,width,height}=drawing, a={x:48,y:18,w:width-62,h:height-56};
  const sx=x=>a.x+(x-xMin)/(xMax-xMin)*a.w,sy=y=>a.y+(1-(y-yMin)/(yMax-yMin))*a.h;
  ctx.textAlign='right';
  for(let i=0;i<=3;i++) {
    const value=yMin+(yMax-yMin)*i/3,y=sy(value);ctx.strokeStyle=colors.grid;ctx.beginPath();ctx.moveTo(a.x,y);ctx.lineTo(a.x+a.w,y);ctx.stroke();ctx.fillStyle=colors.muted;ctx.fillText(format(value,0),a.x-7,y+4);
  }
  ctx.textAlign='center';for(let i=0;i<=4;i++) {const x=xMin+(xMax-xMin)*i/4;ctx.fillText(format(x,0),sx(x),a.y+a.h+18);}
  ctx.fillText(xTitle,a.x+a.w/2,height-2);ctx.textAlign='left';ctx.fillText(yTitle,a.x,10);
  ctx.save();ctx.beginPath();ctx.rect(a.x,a.y,a.w,a.h);ctx.clip();
  for(const seriesItem of series) {
    ctx.beginPath();ctx.strokeStyle=seriesItem.color;ctx.lineWidth=1.5;ctx.setLineDash(seriesItem.dashed?[4,3]:[]);
    seriesItem.values.forEach(([x,y],i)=>i===0?ctx.moveTo(sx(x),sy(y)):ctx.lineTo(sx(x),sy(y)));ctx.stroke();
  }
  ctx.restore();ctx.setLineDash([]);let legendX=width-18;ctx.textAlign='right';
  for(const item of [...series].reverse()) {ctx.fillStyle=item.color;ctx.fillText(item.name,legendX,11);legendX-=ctx.measureText(item.name).width+16;}
}

function renderSignal() {
  if(!state.data) return;
  const data=state.data, ps=data.spectra[state.ps], pl=data.spectra.pl;
  const referencePeak=Math.max(...data.spectra.double.map(magnitude));
  const second=state.difference ? pl.map((z,i)=>[z[0]-ps[i][0],z[1]-ps[i][1]]) : pl;
  $('ps-label').textContent=data.labels[state.ps];
  $('pl-label').textContent=state.difference ? 'PL − 선택 PS · 복소 오차' : data.labels.pl;
  heatmap('ps-map',ps,referencePeak);heatmap('pl-map',second,referencePeak);
  const peak=data.peaks.pl, truth=data.truth, error=data.errors.pl;
  $('truth-value').textContent=truth?`${format(truth.range_m,1)} m / ${format(truth.velocity_mps,1)} m/s`:'기준값 없음';
  $('truth-note').textContent=data.kind==='import'?'사용자 CSV에 기준 표적 정보 없음':'시뮬레이션 설정값 · ＋ 표시';
  $('peak-value').textContent=`${format(peak.range_m,2)} m / ${format(peak.velocity_mps,2)} m/s`;
  $('peak-bin').textContent=`Range ${peak.range_bin} · Doppler ${peak.doppler_bin} (shift 전)`;
  $('truth-error').textContent=truth?`${format(peak.range_m-truth.range_m,2)} m / ${format(peak.velocity_mps-truth.velocity_mps,2)} m/s`:'—';
  $('resolution').textContent=`bin 간격 ${format(data.axes.range_m[1],2)} m · ${format(data.axes.velocity_mps[1]-data.axes.velocity_mps[0],2)} m/s`;
  $('l2-value').textContent=error.relative_l2==null?'정의 불가 (PS 영 신호)':`${format(error.relative_l2*100,4)} %`;
  $('max-error').textContent=`PS double 기준 · 최대 ${format(error.max_complex_q15_lsb,3)} Q15 LSB`;
  const [d,r]=state.selected, index=d*N+r, a=ps[index], b=pl[index];
  $('selected-bin').textContent=`R ${r} / D ${d} · ${format(data.axes.range_m[r],2)} m · ${format(data.axes.velocity_mps[(d+64)%N],2)} m/s`;
  $('selected-ps-label').textContent=state.ps==='double'?'PS double':'PS NEON';
  $('selected-ps').textContent=complex(a);$('selected-pl').textContent=complex(b);
  $('selected-error').textContent=`${format(Math.hypot(b[0]-a[0],b[1]-a[1]),5)} Q15 LSB`;
  $('range-bin').value=r;$('doppler-bin').value=d;
  const domain=bounds(), series=[['PS',ps,colors.ps],['PL',pl,colors.pl]].map(([name,values,color])=>({name,color,values:Array.from({length:domain.r1-domain.r0},(_,i)=>{const r=domain.r0+i;return [data.axes.range_m[r],db(magnitude(values[d*N+r]),referencePeak)];})}));
  lineChart('range-chart',series,data.axes.range_m[domain.r0],data.axes.range_m[domain.r1-1],-70,0,'거리 (m)','dB');
  $('chirp').disabled=!data.input_iq;
  if(data.input_iq) {
    const row=data.input_iq.slice(state.chirp*N,(state.chirp+1)*N),limit=Math.max(1,...row.flat().map(Math.abs))*1.1;
    lineChart('iq-chart',[{name:'I',color:colors.ps,values:row.map((z,i)=>[i,z[0]])},{name:'Q',color:colors.pl,dashed:true,values:row.map((z,i)=>[i,z[1]])}],0,127,-limit,limit,'sample','Q15 입력 단위');
  } else {
    const drawing=canvasContext('iq-chart');if(drawing) {drawing.ctx.fillStyle=colors.muted;drawing.ctx.textAlign='center';drawing.ctx.fillText('입력 I/Q CSV를 함께 가져오면 표시됩니다.',drawing.width/2,drawing.height/2);}
  }
}

const phases=[
 ['PS 입력 준비','원본 I/Q를 프레임 전체에 같은 계수로 양자화합니다. 최초 입력과 최종 출력의 coherent 복사는 유지됩니다.'],
 ['DMA 입력 제출','PS가 한 프레임을 요청합니다. MM2S가 16,384개 복소 샘플, 64 KiB를 PL로 보냅니다.'],
 ['PL Range FFT','각 chirp의 128개 sample을 7단계 FFT 코어에 입력합니다. 한 축에서 128개의 FFT 벡터를 처리합니다.'],
 ['PL 중간 행렬 / 전치','Range 결과를 64 KiB 행렬에 보관하고 열 방향으로 읽습니다. PS 전치와 중간 DDR 왕복을 제거합니다.'],
 ['PL Doppler FFT','같은 7단계 코어를 재사용해 각 range bin의 128개 chirp를 처리합니다. 한 열의 입력이 수락된 후 해당 열의 결과를 덮어씁니다.'],
 ['PL 배열 복원 / DMA 출력','Doppler-major, range-minor 순서로 최종 행렬을 배출합니다. S2MM으로 64 KiB 결과를 PS DDR로 돌려줍니다.'],
 ['PS 결과 사용','출력 복사가 끝나면 PS가 사용할 수 있는 2D 결과가 됩니다. 피크 탐색과 좌표 환산은 별도 후처리입니다.']
];
function renderFlow() {
  const previous=state.arch==='e13';
  document.querySelectorAll('[data-phase]').forEach(el=>el.classList.toggle('active',el.dataset.phase.split(',').map(Number).includes(state.phase)));
  $('ps-transpose').hidden=!previous;$('ps-transpose').classList.toggle('active',previous&&state.phase===3);
  document.querySelector('.matrix-node').hidden=previous;
  document.querySelector('.pl-processor > .flow-node:last-child b').textContent=previous?'FFT 결과 출력':'최종 배열 배출';
  document.querySelector('.pl-processor > .flow-node:last-child span').textContent=previous?'축별 DMA 출력 → PS 배열 복원':'Doppler-major / range-minor';
  $('arch-e14').setAttribute('aria-pressed',String(!previous));$('arch-e13').setAttribute('aria-pressed',String(previous));
  $('architecture-caption').textContent=previous?'이전 E13 · 축당 1 ioctl / 입출력 합 256 KiB':'현재 E14 · 전체 프레임당 1 ioctl / 입출력 합 128 KiB';
  $('tx-size').textContent=previous?'64 KiB × 두 축':'64 KiB 입력';$('rx-size').textContent=previous?'64 KiB × 두 축':'64 KiB 출력';
  const phase=[...phases[state.phase]];
  if(previous) {
    if(state.phase===1) phase[1]='E13은 Range 축과 Doppler 축을 각각 제출합니다. 프레임당 2 ioctl, DMA 채널 제출 4회입니다.';
    if(state.phase===3) {phase[0]='PS 중간 전치';phase[1]='Range 출력을 DDR로 가져온 뒤 PS가 gather/scatter로 Doppler 입력을 구성합니다. 중간 결과의 복사와 DDR 왕복이 필요합니다.';}
    if(state.phase===4) phase[1]='PS에서 전치한 입력을 PL의 같은 FFT 코어로 다시 보내 Doppler 축을 처리합니다.';
    if(state.phase===5) {phase[0]='DMA 출력 / PS 배열 복원';phase[1]='두 번째 축 출력을 DMA로 받고 최종 배열 순서는 PS가 복원합니다. 총 입출력 payload는 256 KiB입니다.';}
  }
  $('fft-role').textContent=state.phase===2?'Range FFT · 동일 코어':state.phase===4?'Doppler FFT · 동일 코어':'Range FFT → Doppler FFT';
  $('matrix-role').textContent=state.phase===3?'Range 행 저장 → Doppler 열 읽기':state.phase===4?'한 열 입력 수락 후 결과 덮어쓰기':state.phase===5?'Doppler-major 순서로 배출':'행 저장 → 열 읽기 → 출력 순서 복원';
  $('phase-number').textContent=`${String(state.phase+1).padStart(2,'0')} / 07`;$('phase-title').textContent=phase[0];$('phase-description').textContent=phase[1];
}
function stopPlayback() {if(state.timer)clearInterval(state.timer);state.timer=null;$('play').textContent='재생';}
function nextPhase() {state.phase=Math.min(6,state.phase+1);renderFlow();if(state.phase===6)stopPlayback();}

function element(tag,className,text) {const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;}
function stackedBar(title,segments,total) {
  const row=element('div','profile-row'),label=element('div','bar-label');label.append(element('span','',title),element('span','',`${format(total,3)} ms`));row.append(label);
  const stack=element('div','stack'),legend=element('div','stack-legend');
  for(const segment of segments) {
    const bar=element('span');bar.style.width=`${segment.value/total*100}%`;bar.style.background=segment.color;bar.title=`${segment.name}: ${format(segment.value,6)} ms`;stack.append(bar);
    const item=element('span'),swatch=element('i');swatch.style.background=segment.color;item.append(swatch,document.createTextNode(`${segment.name} ${format(segment.value,3)}`));legend.append(item);
  }
  row.append(stack,legend);return row;
}
function renderBaseline() {
  if(!state.baseline) return;
  const b=state.baseline, names={double:'PS double',float_neon:'PS float + NEON',pl:'PL E14'}, results=b.comparison.results;
  const limit=Math.max(...Object.values(results).map(x=>x.timing.max_ms))*1.03;
  $('latency-bars').replaceChildren();$('timing-table').replaceChildren();
  for(const key of ['double','float_neon','pl']) {
    const t=results[key].timing,row=element('div','latency-row'),label=element('div','bar-label');label.append(element('span','',names[key]),element('strong','',`${format(t.median_ms,3)} ms`));
    const track=element('div','bar-track'),fill=element('div','bar-fill'),whisker=element('span','whisker');fill.style.width=`${t.median_ms/limit*100}%`;whisker.style.left=`${t.p05_ms/limit*100}%`;whisker.style.width=`${(t.p95_ms-t.p05_ms)/limit*100}%`;track.append(fill,whisker);row.append(label,track);$('latency-bars').append(row);
    const tr=element('tr');for(const value of [names[key],t.count,...['mean_ms','median_ms','p05_ms','p95_ms','max_ms'].map(k=>format(t[k],3))])tr.append(element('td','',value));$('timing-table').append(tr);
  }
  $('speedup').textContent=`${format(b.progression.paired_neon_speedup,3)}×`;
  const p=b.profile, m=p.mean_ms;$('profile-bars').replaceChildren();
  $('profile-bars').append(stackedBar('Host 전체',[{name:'입력 복사',value:m.host_input_copy_ms,color:colors.ps},{name:'ioctl',value:m.ioctl_ms,color:'#486f9e'},{name:'출력 복사',value:m.host_output_copy_ms,color:colors.amber},{name:'잔여',value:p.host_residual_ms,color:'#748194'}],m.wall_ms));
  $('profile-bars').append(stackedBar('ioctl 내부',[{name:'입력 복사',value:m.kernel_copy_in_ms,color:colors.ps},{name:'제출',value:m.kernel_submit_ms,color:'#a89de9'},{name:'대기',value:m.kernel_wait_ms,color:'#486f9e'},{name:'검사',value:m.kernel_check_ms,color:'#829dbe'},{name:'출력 복사',value:m.kernel_copy_out_ms,color:colors.amber},{name:'잔여',value:p.ioctl_residual_ms,color:'#748194'}],m.ioctl_ms));
  $('profile-bars').append(stackedBar('PL active · 대기와 중첩',[{name:'Range',value:p.phase_ms.range_cycles,color:colors.pl},{name:'Doppler',value:p.phase_ms.doppler_cycles,color:'#389a9b'},{name:'배출',value:p.phase_ms.drain_cycles,color:colors.amber}],m.pl_active_ms));
  $('profile-note').textContent='각 막대는 자체 합계 기준입니다. ioctl은 Host 안에, PL active는 ioctl 대기 안에 포함되므로 세 막대를 더하지 않습니다.';
  $('measurement-scope').textContent=b.scope+' · '+b.excluded+' · 출처: '+b.source;
  const h=b.progression;$('history-facts').replaceChildren();
  for(const [name,value] of [['프레임당 DMA payload','256 → 128 KiB'],['중간 전치 담당','PS → PL'],['과거 PL 중앙값 비교',`${format(h.previous_median_ms,3)} → ${format(h.current_median_ms,3)} ms`]]) {
    const div=element('div');div.append(element('span','',name),element('b','',value));$('history-facts').append(div);
  }
  $('counter-grid').replaceChildren();const counters=p.frame_counters_mean;
  for(const [label,key] of [['행렬 읽기','matrix_reads'],['행렬 쓰기','matrix_writes'],['행렬 크기 / words','matrix_words'],['덮어쓰기 guard','overwrite_errors'],['Range cycles','range_cycles'],['Doppler cycles','doppler_cycles'],['Drain cycles','drain_cycles'],['겹치는 단계 CALC / cycles','multi_stage_cycles']]) {
    const div=element('div','counter');div.append(element('span','',label),element('b','',format(counters[key],key==='range_cycles'?1:0)));$('counter-grid').append(div);
  }
}

document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{
  if(button.dataset.view!=='architecture')stopPlayback();
  document.querySelectorAll('[data-view]').forEach(tab=>{const active=tab===button;tab.classList.toggle('active',active);tab.setAttribute('aria-selected',String(active));$('view-'+tab.dataset.view).hidden=!active;});
  requestAnimationFrame(renderSignal);
}));
for(const [input,output,unit] of [['target-range','range-output','m'],['target-speed','speed-output','m/s'],['target-snr','snr-output','dB']])$(input).addEventListener('input',()=>{$(output).textContent=`${$(input).value} ${unit}`;});
$('simulation-form').addEventListener('submit',async event=>{
  event.preventDefault();if(state.busy)return;busy(true);message('시뮬레이션 입력과 Q15 모델을 계산하고 있습니다…');
  try {activate(await api('/api/simulate',{engine:$('engine').value,range_m:Number($('target-range').value),velocity_mps:Number($('target-speed').value),snr_db:Number($('target-snr').value)}),'simulation-'+(++state.serial));}catch(error){message(error.message,true);}finally{busy(false);}
});
$('engine').addEventListener('change',()=>{const radar=$('engine').value==='radarsimpy';$('target-snr').disabled=radar;$('engine-note').textContent=radar?'기존 sender의 RadarSimPy 실행 · SNR 슬라이더 미적용 · PL은 Q15 소프트웨어 모델':'복소 beat-tone + 잡음 모델 · NumPy와 PL Q15 모델 비교';});
$('reload').addEventListener('click',async()=>{if(state.busy)return;busy(true);try{activate(await api('/api/recording'),'recording');}catch(error){message(error.message,true);}finally{busy(false);}});
$('session').addEventListener('change',()=>{const data=state.sessions.get($('session').value);if(data)activate(data,$('session').value);});
$('ps-variant').addEventListener('change',()=>{state.ps=$('ps-variant').value;renderSignal();});
for(const [id,key] of [['difference','difference'],['fit','fit']])$(id).addEventListener('click',()=>{state[key]=!state[key];$(id).setAttribute('aria-pressed',String(state[key]));renderSignal();});
$('select-peak').addEventListener('click',()=>{if(state.data){state.selected=[state.data.peaks.pl.doppler_bin,state.data.peaks.pl.range_bin];renderSignal();}});
for(const id of ['ps-map','pl-map'])$(id).addEventListener('click',event=>{
  if(!state.data || !$(id)._plot)return;
  const {area:a,b}=$(id)._plot,rect=$(id).getBoundingClientRect(),x=event.clientX-rect.left,y=event.clientY-rect.top;
  if(x<a.x||x>=a.x+a.w||y<a.y||y>=a.y+a.h)return;
  const r=b.r0+Math.floor((x-a.x)/a.w*(b.r1-b.r0)),sd=b.d1-1-Math.floor((y-a.y)/a.h*(b.d1-b.d0));state.selected=[(sd+64)%N,r];renderSignal();
});
for(const [id,index] of [['range-bin',1],['doppler-bin',0]]) {
  const update=()=>{if($(id).value==='')return;const value=Number($(id).value);if(Number.isInteger(value)&&value>=0&&value<128){state.selected[index]=value;renderSignal();}};
  $(id).addEventListener('input',update);$(id).addEventListener('change',()=>{update();$(id).value=state.selected[index];});
}
$('chirp').addEventListener('input',()=>{if($('chirp').value==='')return;state.chirp=Math.max(0,Math.min(127,Math.round(Number($('chirp').value)||0)));$('chirp').value=state.chirp;renderSignal();});
$('play').addEventListener('click',()=>{if(state.timer){stopPlayback();return;}if(state.phase===6)state.phase=0;renderFlow();$('play').textContent='일시 정지';state.timer=setInterval(nextPhase,1200);});
$('step').addEventListener('click',()=>{stopPlayback();state.phase=(state.phase+1)%7;renderFlow();});
$('reset').addEventListener('click',()=>{stopPlayback();state.phase=0;renderFlow();});
for(const arch of ['e14','e13'])$('arch-'+arch).addEventListener('click',()=>{stopPlayback();state.arch=arch;renderFlow();});
$('open-import').addEventListener('click',()=>{$('import-error').textContent='';$('import-dialog').showModal();});
$('close-import').addEventListener('click',()=>$('import-dialog').close());
$('import-form').addEventListener('submit',async event=>{
  event.preventDefault();if(state.busy)return;busy(true);$('import-error').textContent='';
  try {
    const ps=$('ps-file').files[0],pl=$('pl-file').files[0],input=$('input-file').files[0];
    if([ps,pl,input].filter(Boolean).some(f=>f.size>3*1024*1024))throw new Error('각 CSV 파일은 3 MiB 이하여야 합니다.');
    const values={ps_csv:await ps.text(),pl_csv:await pl.text(),input_csv:input?await input.text():null,radar:{sample_rate_hz:Number($('import-fs').value)*1e6,bandwidth_mhz:Number($('import-bandwidth').value),chirp_us:Number($('import-chirp').value),prp_us:Number($('import-prp').value),fc_ghz:Number($('import-fc').value)}};
    const data=await api('/api/import',values);activate(data,'import-'+(++state.serial));$('import-dialog').close();
  }catch(error){$('import-error').textContent=error.message;}finally{busy(false);}
});
$('export').addEventListener('click',()=>{
  if(!state.data)return;
  const data={schema:'fmcw-dashboard-analysis-v1',exported_at:new Date().toISOString(),frame:state.data,selection:{doppler_bin_unshifted:state.selected[0],range_bin:state.selected[1],ps_variant:state.ps},board_baseline_reference:state.baseline?{source:state.baseline.source,scope:state.baseline.scope,note:'고정 기준 프레임의 과거 보드 기록; 활성 프레임의 측정이 아님'}:null};
  const url=URL.createObjectURL(new Blob([JSON.stringify(data)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=`fmcw-analysis-${state.data.kind}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
let scheduled=false;
new ResizeObserver(()=>{if(!scheduled){scheduled=true;requestAnimationFrame(()=>{scheduled=false;renderSignal();});}}).observe(document.querySelector('main'));
window.addEventListener('pagehide',stopPlayback);

async function initialize() {
  busy(true);renderFlow();
  const [frame,baseline]=await Promise.allSettled([api('/api/recording'),api('/api/baseline')]);
  if(frame.status==='fulfilled')activate(frame.value,'recording');else message(frame.reason.message,true);
  if(baseline.status==='fulfilled'){state.baseline=baseline.value;renderBaseline();}else message('성능 기록을 읽지 못했습니다: '+baseline.reason.message,true);
  busy(false);
}
initialize().catch(error=>{busy(false);message(error.message,true);});
