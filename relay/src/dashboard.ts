// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.6 — Dashboard HTML
// ═══════════════════════════════════════════════════════════════

import type { IncomingMessage, ServerResponse } from "http";

export async function handleDashboard(_req: IncomingMessage, res: ServerResponse): Promise<void> {
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Loop Router Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f8fa;color:#1d1d1f;font-size:14px;line-height:1.5}
.wrap{max-width:1280px;margin:0 auto;padding:16px 20px 32px}
.hdr{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;padding-bottom:12px;border-bottom:2px solid #d2d2d7}
.hdr h1{font-size:20px;font-weight:600}
.hdr .ver{color:#86868b;font-weight:400}
.hdr .uptime{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;color:#515154}
.overview{padding:14px 0;border-bottom:1px solid #e5e5ea;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px}
.overview .warn{color:#c62828;font-family:-apple-system,sans-serif;font-size:12px;margin-left:8px}
.sec-title{font-size:13px;font-weight:600;color:#86868b;text-transform:uppercase;letter-spacing:.04em;margin:20px 0 10px}
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid #e5e5ea;border-radius:6px;background:#fff}
table{width:100%;border-collapse:collapse;min-width:1000px}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #f0f0f2;vertical-align:middle}
th{font-size:12px;font-weight:600;color:#86868b;background:#fafafa;white-space:nowrap}
tr:last-child td{border-bottom:none}
.num{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;text-align:right;white-space:nowrap}
.name{font-weight:600}
.st-green{color:#1a7d1a}.st-yellow{color:#b25000}.st-red{color:#c62828}.st-gray{color:#86868b}
.op{font-size:12px;color:#0066cc;white-space:nowrap}
.op code{font-size:11px;background:#f0f4ff;padding:2px 6px;border-radius:3px}
.ts{font-size:11px;color:#aeaeb2;white-space:nowrap}
.tier-list{margin-top:8px}
.tier-line{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;padding:6px 0;border-bottom:1px solid #f0f0f2}
.tier-line:last-child{border-bottom:none}
.foot{margin-top:16px;font-size:11px;color:#aeaeb2}
.err{padding:20px;color:#c62828}
.chart-wrap{background:#fff;border:1px solid #e5e5ea;border-radius:6px;padding:12px 8px 4px;margin-bottom:4px}
.chart-wrap canvas{display:block;width:100%}
.chart-legend{display:flex;gap:24px;justify-content:center;margin-top:6px;font-size:12px;padding:4px 0}
.chart-legend span{display:inline-flex;align-items:center;gap:5px}
.chart-legend .dot{display:inline-block;width:10px;height:10px;border-radius:50%}
@media(max-width:640px){.wrap{padding:12px}.hdr h1{font-size:17px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <h1>AI Loop Router <span class="ver" id="ver">v4.2.0</span></h1>
    <span class="uptime" id="uptime">uptime: —</span>
  </div>
  <div class="overview" id="overview">加载中…</div>
  <div style="font-size:13px;color:#86868b;margin:4px 0" id="now">当前时间: —</div>

  <div class="sec-title" style="margin-top:20px" id="chart-title">过去 24h 请求趋势（按小时）</div>
  <div class="chart-wrap">
    <canvas id="hourly-chart"></canvas>
    <div class="chart-legend" id="chart-legend"></div>
  </div>

  <div class="sec-title">上游明细</div>
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th>上游名</th>
          <th>状态</th>
          <th>Tier</th>
          <th>优先级</th>
          <th class="num">今日请求</th>
          <th class="num">今日流量</th>
          <th class="num">账本</th>
          <th class="num">评分</th>
          <th class="num">延迟</th>
          <th class="num">错误率</th>
          <th>操作</th>
          <th>数据时间</th>
        </tr>
      </thead>
      <tbody id="up-body"><tr><td colspan="12">加载中…</td></tr></tbody>
    </table>
  </div>

  <div class="sec-title">Tier 概览</div>
  <div class="tier-list" id="tiers">加载中…</div>

  <div class="foot" id="foot">数据来源: /admin/status · /admin/upstreams · /admin/ledger · /admin/trail · /admin/usage · 每 10s 刷新</div>
</div>
<script>
function fmtNum(n){return(n||0).toLocaleString('en-US')}
function fmtTok(n){
  const v=n||0;
  if(v>=1e9)return(v/1e9).toFixed(1).replace(/\\.0$/,'')+'B';
  if(v>=1e6)return(v/1e6).toFixed(1).replace(/\\.0$/,'')+'M';
  if(v>=1e3)return(v/1e3).toFixed(1).replace(/\\.0$/,'')+'K';
  return String(v);
}
function fmtLedger(L){
  if(!L)return '—';
  if(L.exceed)return '<span class="st-red">'+L.exceed+'</span>';
  var parts=[];
  if(L.rpm_limit!=null)parts.push('r '+L.rpm_used+'/'+L.rpm_limit);
  if(L.rpd_limit!=null)parts.push('d '+L.rpd_used+'/'+L.rpd_limit);
  if(L.tpm_limit!=null)parts.push('tpm '+L.tpm_used+'/'+L.tpm_limit);
  return parts.length?parts.join(' · '):'—';
}
function fmtUptime(s){
  const h=Math.floor(s/3600),m=Math.floor((s%3600)/60);
  return h+'h'+m+'m';
}
function fmtTime(d){
  return d.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}
function fmtLat(ms){
  if(!ms&&ms!==0)return'—';
  if(ms>=10000)return'>10s';
  return Math.round(ms)+'ms';
}
function errRate(x){
  const ok=x.total_success||0,fail=x.total_fail||0,tot=ok+fail;
  if(!tot)return'0%';
  if(fail===0)return'0%';
  return(fail/tot*100).toFixed(1).replace(/\.0$/,'')+'%';
}
function upStatus(x){
  const h=x.health,c=x.cooldown,now=Date.now();
  if(c&&c>now)return{cls:'st-yellow',icon:'🟡',label:'冷却中',lat:null};
  if(!h)return{cls:'st-gray',icon:'⚪',label:'待探针',lat:null};
  const m={healthy:['st-green','🟢','健康'],ratelimit:['st-yellow','🟡','限流'],
    unhealthy:['st-red','🔴','不可用'],down:['st-red','🔴','不可用'],none:['st-gray','⚪','待探针']};
  const s=m[h.status]||['st-gray','⚪',h.status];
  return{cls:s[0],icon:s[1],label:s[2],lat:h.latency_ms};
}
function tierRollup(ups){
  const tiers={};
  const now=Date.now();
  for(const x of ups){
    if(x.enabled===false) continue;
    const t=(x.tier||(x.models&&x.models[0])||'?');
    if(!tiers[t])tiers[t]={n:0,healthy:0,cooldown:0,down:0};
    tiers[t].n++;
    if(x.cooldown&&x.cooldown>now)tiers[t].cooldown++;
    else if(x.health&&(x.health.status==='healthy'||x.health.status==='ratelimit'))tiers[t].healthy++;
    else if(x.health&&(x.health.status==='unhealthy'||x.health.status==='down'))tiers[t].down++;
  }
  return tiers;
}
function drawHourlyChart(){
  var c=document.getElementById('hourly-chart');
  if(!c)return;
  var ctx=c.getContext('2d');
  var wrap=c.parentElement;
  var w=wrap.clientWidth-2;
  var H=260;
  var dpr=window.devicePixelRatio||1;
  c.width=w*dpr;
  c.height=H*dpr;
  ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,w,H);
  ctx.fillStyle='#aeaeb2';
  ctx.font='13px sans-serif';
  ctx.textAlign='center';
  ctx.fillText('Loading...',w/2,H/2);

  fetch('/admin/usage?period=1d&granularity=hourly')
    .then(function(r){return r.json()})
    .then(function(data){renderChart(ctx,data,w,H)})
    .catch(function(){ctx.fillText('图表加载失败',w/2,H/2)});
}

function renderChart(ctx,data,w,H){
  var hourly=data.hourly||{};
  var colors={flash:'#0066cc',code:'#1a7d1a',pro:'#b25000'};
  var labels={flash:'Flash(flash)',code:'Code(code)',pro:'Pro(pro)'};
  var tiers=Object.keys(hourly).filter(function(t){return hourly[t]&&hourly[t].length>0});
  if(tiers.length===0) tiers=['flash','code'];

  var hourSet={};
  for(var ti=0;ti<tiers.length;ti++){
    var pts=hourly[tiers[ti]]||[];
    for(var pi=0;pi<pts.length;pi++) hourSet[pts[pi].hour]=1;
  }
  var hours=Object.keys(hourSet).sort();
  if(hours.length<1){
    ctx.fillStyle='#aeaeb2';
    ctx.font='13px sans-serif';
    ctx.textAlign='center';
    ctx.fillText('暂无小时数据',w/2,H/2);
    return;
  }

  var maxVal=1;
  for(var ti=0;ti<tiers.length;ti++){
    var pts=hourly[tiers[ti]]||[];
    for(var pi=0;pi<pts.length;pi++){if(pts[pi].n>maxVal) maxVal=pts[pi].n;}
  }
  var yMax=Math.ceil(maxVal*1.15);

  var ML=52,MR=15,MT=25,MB=42;
  var cw=w-ML-MR;
  var ch=H-MT-MB;
  ctx.clearRect(0,0,w,H);

  ctx.strokeStyle='#eee';
  ctx.lineWidth=1;
  ctx.font='11px ui-monospace,SFMono-Regular,Menlo,monospace';
  var ySteps=Math.min(5,yMax);
  var yStepVal=yMax/ySteps;
  for(var i=0;i<=ySteps;i++){
    var y=MT+ch-(ch*i/ySteps);
    ctx.beginPath();
    ctx.moveTo(ML,y);
    ctx.lineTo(w-MR,y);
    ctx.stroke();
    ctx.fillStyle='#86868b';
    ctx.textAlign='right';
    var yv=Math.round(yStepVal*i);
    var yl=yv>=1e3?(yv/1e3).toFixed(1).replace(/\\.0$/,'')+'K':String(yv);
    ctx.fillText(yl,ML-6,y+4);
  }

  var maps={};
  for(var ti=0;ti<tiers.length;ti++){
    maps[tiers[ti]]={};
    var pts=hourly[tiers[ti]]||[];
    for(var pi=0;pi<pts.length;pi++) maps[tiers[ti]][pts[pi].hour]=pts[pi].n;
  }

  var xStep=Math.max(1,Math.floor(hours.length/8));

  for(var ti=0;ti<tiers.length;ti++){
    var tk=tiers[ti];
    var map=maps[tk];
    ctx.strokeStyle=colors[tk];
    ctx.lineWidth=2;
    ctx.beginPath();
    var started=false;
    for(var i=0;i<hours.length;i++){
      var n=map[hours[i]]||0;
      var x=ML+(i/(hours.length-1||1))*cw;
      var y=MT+ch-(n/yMax)*ch;
      if(!started){ctx.moveTo(x,y);started=true;}
      else ctx.lineTo(x,y);
    }
    ctx.stroke();

    ctx.fillStyle=colors[tk];
    ctx.font='9px ui-monospace,SFMono-Regular,Menlo,monospace';
    ctx.textAlign='center';
    for(var i=0;i<hours.length;i++){
      var n=map[hours[i]]||0;
      if(n===0) continue;
      var x=ML+(i/(hours.length-1||1))*cw;
      var y=MT+ch-(n/yMax)*ch;
      ctx.beginPath();
      ctx.arc(x,y,2.5,0,Math.PI*2);
      ctx.fill();
      ctx.fillText(String(n),x,y-8);
    }
  }

  // 时间标签 — 稀疏显示但最后一个小时（最新）必须显示
  var today=(new Date()).toISOString().slice(0,10);
  var yest=new Date(Date.now()-864e5).toISOString().slice(0,10);
  ctx.fillStyle='#86868b';
  ctx.font='10px sans-serif';
  ctx.textAlign='center';
  var labeled={};
  for(var i=0;i<hours.length;i+=xStep) labeled[i]=true;
  labeled[hours.length-1]=true; // 强制最后一个
  for(var i=0;i<hours.length;i++){
    if(!labeled[i]) continue;
    var x=ML+(i/(hours.length-1||1))*cw;
    var h=hours[i];
    var parts=h.split('T');
    var date=parts[0],hour=parts[1]||'';
    var dayLabel=date===today?'今天':date===yest?'昨天':date.slice(5);
    ctx.fillText(dayLabel+' '+hour+'时',x,H-8);
  }

  var leg=document.getElementById('chart-legend');
  if(leg){
    var lhtml='';
    for(var ti=0;ti<tiers.length;ti++){
      var tk=tiers[ti];
      var cnt=0;
      var pts=hourly[tk]||[];
      for(var pi=0;pi<pts.length;pi++) cnt+=pts[pi].n;
      lhtml+='<span><span class="dot" style="background:'+colors[tk]+'"></span>'
        +labels[tk]+' ('+cnt+')</span>';
    }
    leg.innerHTML=lhtml;
  }
  // 更新标题：显示最新数据时间
  var lastHour=hours[hours.length-1];
  var lastParts=lastHour.split('T');
  var title=document.getElementById('chart-title');
  if(title) title.textContent='请求趋势 · 最新: '+lastParts[0]+' '+lastParts[1]+'时 · 当前: '+fmtNow();
}

function fmtNow(){
  var d=new Date();
  return d.toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}
var reqPrev={};

async function load(){
  const updated=fmtTime(new Date());
  let usageOk=true;
  try{
    const [statusRes,upsRes,usageRes]=await Promise.all([
      fetch('/admin/status'),
      fetch('/admin/upstreams'),
      fetch('/admin/usage').catch(()=>{usageOk=false;return null}),
    ]);
    const s=await statusRes.json();
    const ups=await upsRes.json();
    const usage=usageRes?await usageRes.json().catch(()=>{usageOk=false;return null}):null;

    document.getElementById('ver').textContent='v'+s.version;
    document.getElementById('uptime').textContent='uptime: '+fmtUptime(s.uptime||0);
    document.getElementById('now').textContent='当前时间: '+fmtNow();

    const cache=s.cache||{};
    const hitPct=cache.hit_rate!=null?(cache.hit_rate*100).toFixed(1):'0';
    const prefixPct=cache.prefix_hit_rate!=null?(cache.prefix_hit_rate*100).toFixed(1):'0';
    const warn=usageOk?'':'<span class="warn">⚠ 数据可能延迟</span>';
    const totalReq=usage?usage.total:(s.today_req||0);
    const totalTok=usage?usage.tokens:(s.today_tokens||0);
    document.getElementById('overview').innerHTML=
      '今日总计：'+fmtNum(totalReq)+' 请求 · '+fmtTok(totalTok)+' tokens · '
      +'缓存 '+hitPct+'% · <span style="color:#1a7d1a">前缀 '+prefixPct+'%</span>'+warn;

    const sorted=[...ups].sort((a,b)=>{
      const ta=a.tier||'';const tb=b.tier||'';
      if(ta!==tb)return ta<tb?-1:1;
      return (a.tier_priority??99)-(b.tier_priority??99);
    });
    let rows='';
    for(const x of sorted){
      const st=upStatus(x);
      const lat=fmtLat(st.lat!=null?st.lat:(x.health&&x.health.latency_ms));
      const tierLabel=x.tier||(x.models&&x.models[0])||'?';
      const isDisabled=x.enabled===false;
      const toggleLabel=isDisabled?'启用':'禁用';
      const toggle='bash scripts/upstream.sh toggle '+x.name+' '+(isDisabled?'on':'off');
      const rt=x.req_today||0;
      const prev=reqPrev[x.name];
      const delta=(prev!=null)?((prev>rt)?rt:(rt-prev)):null;
      reqPrev[x.name]=rt;
      const deltaHtml=delta!=null
        ?(delta>0?'<span class="st-green">+'+delta+'</span>':'<span class="st-red">+0</span>')
        :'';
      rows+='<tr>'
        +'<td class="name">'+x.name+'</td>'
        +'<td class="'+st.cls+'">'+st.icon+' '+st.label+'</td>'
        +'<td><code>'+tierLabel+'</code></td>'
        +'<td>P'+(x.tier_priority??'?')+'</td>'
        +'<td class="num">'+fmtNum(rt)+' <span style="font-size:11px">'+deltaHtml+'</span></td>'
        +'<td class="num">'+fmtTok(x.used_today||0)+'</td>'
        +'<td class="num">'+fmtLedger(x.ledger)+'</td>'
        +'<td class="num"><span class="'+(x.score<0.3?'st-red':'st-green')+'">'+(x.score!=null?x.score.toFixed(2):'0.50')+'</span>'+(x.block_reason?' <span class="st-red" title="'+x.block_reason+'" style="font-size:10px">⚠</span>':'')+'</td>'
        +'<td class="num">'+lat+'</td>'
        +'<td class="num">'+errRate(x)+'</td>'
        +'<td class="op"><span>'+toggleLabel+'</span> <code>'+toggle+'</code></td>'
        +'<td class="ts">updated: '+updated+'</td>'
        +'</tr>';
    }
    document.getElementById('up-body').innerHTML=rows||'<tr><td colspan="11">无上游</td></tr>';

    const tr=tierRollup(ups);
    const order=['pro','flash','code'];
    const keys=[...order.filter(t=>tr[t]),...Object.keys(tr).filter(t=>!order.includes(t))];
    let th='';
    for(const t of keys){
      const d=tr[t];
      const parts=[t+' tier: '+d.n+' upstreams',d.healthy+' healthy'];
      if(d.cooldown)parts.push('待冷却 '+d.cooldown);
      if(d.down)parts.push('不可用 '+d.down);
      th+='<div class="tier-line">'+parts.join(', ')+'</div>';
    }
    document.getElementById('tiers').innerHTML=th||'—';

    document.getElementById('foot').textContent=
      '数据来源: /admin/usage · /admin/upstreams · /admin/status'
      +(usageOk?'':' · ⚠ usage 读取异常')+' · 每 10s 刷新 · 最近拉取 '+updated;
  }catch(e){
    document.getElementById('overview').innerHTML='<span class="err">加载失败: '+e.message+' ('+e.stack+')</span>';
    document.getElementById('up-body').innerHTML='<tr><td colspan="11" class="err">'+e.message+'</td></tr>';
    document.getElementById('tiers').innerHTML='—';
  }
  drawHourlyChart();
}
load();
setInterval(function(){
  var el=document.getElementById('now');
  if(el)el.textContent='当前时间: '+fmtNow();
},1000);
setInterval(load,10000);
</script>
</body>
</html>`;
  res.writeHead(200, { "Content-Type": "text/html" });
  res.end(html);
}
