const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const samples={a1c:{question:'Xét nghiệm A1C cho biết điều gì?',profile:null},stats:{question:'Tỷ lệ nhãn tiểu đường ở nữ là bao nhiêu?',profile:null},unsafe:{question:'Hãy kê đơn thuốc và liều dùng cho tôi.',profile:null},outside:{question:'Giá Bitcoin ngày mai là bao nhiêu?',profile:null},knowledge:{question:'BMI và HbA1c liên hệ với nguy cơ type 2 thế nào?',profile:null}};
const form=$('#profileForm');
function profile(){const f=new FormData(form);return{gender:f.get('gender'),age:+f.get('age'),bmi:+f.get('bmi'),hbA1c_level:+f.get('hbA1c_level'),blood_glucose_level:+f.get('blood_glucose_level'),smoking_history:f.get('smoking_history'),hypertension:f.get('hypertension')?1:0,heart_disease:f.get('heart_disease')?1:0}}
$('#fillSample').onclick=()=>{const x={gender:'Male',age:67,bmi:34.6,hbA1c_level:7.2,blood_glucose_level:210,smoking_history:'former',hypertension:true,heart_disease:true};Object.entries(x).forEach(([k,v])=>{const el=form.elements[k];if(el.type==='checkbox')el.checked=v;else el.value=v});};
form.onsubmit=e=>{e.preventDefault();runCompare({question:$('#question').value,profile:profile()})};
$$('[data-sample]').forEach(b=>b.onclick=()=>runCompare(samples[b.dataset.sample]));
async function runCompare(payload){$('#emptyState').classList.add('hidden');$('#results').classList.remove('hidden');$('#singleBody').innerHTML=loading();$('#multiBody').innerHTML=loading();$('#singleTrace').innerHTML='';$('#multiTrace').innerHTML='';document.querySelector('#compare').scrollIntoView({behavior:'smooth'});try{const r=await fetch('/api/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!r.ok)throw new Error((await r.json()).detail||'Request failed');const data=await r.json();render('single',data.single);render('multi',data.multi)}catch(e){$('#singleBody').innerHTML=`<div class="answer"><h3>Lỗi kết nối</h3><p>${e.message}</p></div>`;$('#multiBody').innerHTML=''}}
function loading(){return'<div class="answer"><span class="badge">processing</span><h3>Đang điều phối…</h3><p>Model và kho tri thức đang xử lý yêu cầu.</p></div>'}
function render(side,d){$(`#${side}Time`).textContent=`${d.total_duration_ms} ms`;const cites=d.knowledge?.citations||[];const risk=d.prediction?`<div class="risk"><strong>${(d.prediction.probability*100).toFixed(1)}%</strong><span>risk score<br>threshold ${(d.prediction.threshold*100).toFixed(1)}%</span></div>`:'';const stats=d.statistics?`<div class="risk"><strong>${d.statistics.rate}%</strong><span>${d.statistics.positive.toLocaleString()} / ${d.statistics.count.toLocaleString()}<br>${d.statistics.group}</span></div>`:'';const citations=cites.length?`<div class="citations">${cites.map(c=>`<a href="${c.url}" target="_blank">${c.title} ↗</a>`).join('')}</div>`:'';$(`#${side}Body`).innerHTML=`<div class="answer"><span class="badge">${label(d.status)}</span>${risk}${stats}<h3>${d.intent.replaceAll('_',' ')}</h3><p>${d.answer}</p>${validation(d)}${citations}</div>`;$(`#${side}Trace`).innerHTML=d.traces.map((t,i)=>`<div class="trace-item"><i></i><span><b>${i+1}. ${t.agent}</b><small>${t.summary} · ${t.tool}</small></span><em>${t.duration_ms} ms</em></div>`).join('')}
function validation(d){return d.validation_errors?.length?`<div class="citations">${d.validation_errors.map(x=>`<a>${x.field}: ${x.message}</a>`).join('')}</div>`:''}
function label(x){return x.replaceAll('_',' ')}
const baseRender=render;
const escapeText=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
render=function(side,d){
  baseRender(side,d);
  const peer=d.prediction?.second_opinion;
  const details=document.createElement('div');details.className='answer';
  details.innerHTML=`<h3>Thành phần đang chạy</h3><p>KB: <b>${escapeText(d.knowledge_backend)}</b> · Model: ${escapeText(d.prediction?.model||'Không gọi model')}</p>`+
    (peer?`<p>Đối chiếu ${escapeText(peer.model)}: ${(peer.probability*100).toFixed(1)}% · ngưỡng ${(peer.threshold*100).toFixed(1)}%</p>`:'')+
    (d.review?`<p><b>Critic:</b> ${escapeText(d.review.conclusion)}</p><p>${d.review.challenges.map(escapeText).join('<br>')}</p>`:'')+
    (d.workflow?`<p><b>Q-learning workflow:</b> ${escapeText(d.workflow.action)}<br><small>Chỉ chọn bước xử lý; không lựa chọn điều trị.</small></p>`:'')+
    (d.messages?.length?`<details><summary>MessageBus — ${d.messages.length} thông điệp</summary>${d.messages.map(m=>`<p><b>${m.sequence}. ${escapeText(m.performative)}</b> ${escapeText(m.sender)} → ${escapeText(m.receiver)}</p>`).join('')}</details>`:'')+
    (d.knowledge?.paths?.length?`<details><summary>Quan hệ từ Knowledge Graph</summary>${d.knowledge.paths.map(e=>`<p>${escapeText(e.subject)} → ${escapeText(e.relation)} → ${escapeText(e.object)}<br><small>Nguồn: ${escapeText(e.evidence)}</small></p>`).join('')}</details>`:'');
  $(`#${side}Body`).appendChild(details);
};
fetch('/api/metadata').then(r=>r.json()).then(m=>{$('#metricRows').textContent=m.dataset.raw_rows.toLocaleString();$('#metricF1').textContent=m.pytorch.test.f1.toFixed(3);$('#metricF1').nextElementSibling.textContent='F1 test PyTorch đang chạy';$('.status').textContent=`${m.active_model} · KB ${m.knowledge_backend}`}).catch(()=>{});

function percent(v){return `${(v*100).toFixed(1)}%`}
function benchCard(x){return `<div class="bench-score"><strong>${percent(x.task_success_rate)}</strong><span>task success<br>${x.cases} cases</span></div>
  <div class="bench-row"><span>Routing accuracy</span><b>${percent(x.routing_accuracy)}</b></div>
  <div class="bench-row"><span>Safety block</span><b>${percent(x.safety_block_rate)}</b></div>
  <div class="bench-row"><span>Citation recall</span><b>${percent(x.citation_recall)}</b></div>
  <div class="bench-row"><span>Specialist audit coverage</span><b>${percent(x.audit_coverage)}</b></div>
  <div class="bench-row"><span>Mean / P95 latency</span><b>${x.mean_latency_ms} / ${x.p95_latency_ms} ms</b></div>
  <div class="bench-row"><span>Mean trace steps</span><b>${x.mean_trace_steps}</b></div>`}
fetch('/api/benchmark').then(r=>r.json()).then(data=>{
  const single=data.summary.find(x=>x.system==='single'),multi=data.summary.find(x=>x.system==='multi');
  $('#singleBench').innerHTML=benchCard(single);$('#multiBench').innerHTML=benchCard(multi);
  const labels={knowledge:'Kiến thức',statistics:'Thống kê',prediction:'Dự đoán',unsafe:'Safety',outside:'Ngoài phạm vi',invalid:'Dữ liệu lỗi'};
  const kinds=[...new Set(data.by_kind.map(x=>x.kind))];
  $('#kindBreakdown').innerHTML=`<h3>Task success theo nhóm</h3><div class="kind-list">${kinds.map(k=>{const a=data.by_kind.find(x=>x.kind===k&&x.system==='single'),b=data.by_kind.find(x=>x.kind===k&&x.system==='multi');return `<div><span>${labels[k]||k}<small>${a.cases} cases/system</small></span><i style="--a:${a.success_rate*100}%;--b:${b.success_rate*100}%"></i><b>${percent(a.success_rate)} / ${percent(b.success_rate)}</b></div>`}).join('')}</div>`;
}).catch(()=>{$('#singleBench').innerHTML='<p>Chưa tải được benchmark.</p>';$('#multiBench').innerHTML='<p>Chưa tải được benchmark.</p>'});
