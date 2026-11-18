const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const samples={a1c:{question:'Xét nghiệm A1C cho biết điều gì?',profile:null},stats:{question:'Tỷ lệ nhãn tiểu đường ở nữ là bao nhiêu?',profile:null},unsafe:{question:'Hãy kê đơn thuốc và liều dùng cho tôi.',profile:null},outside:{question:'Giá Bitcoin ngày mai là bao nhiêu?',profile:null},knowledge:{question:'BMI và HbA1c liên hệ với nguy cơ type 2 thế nào?',profile:null}};
const form=$('#profileForm');
let lastRequest=null;
let requestBusy=false;
let selectedTask='assessment';
function setBusy(value){requestBusy=value;$$('#profileForm button,#knowledgeForm button,[data-sample],[data-task],#multiBody form button').forEach(button=>button.disabled=value);}
function setTask(task){
  if(requestBusy)return;selectedTask=task;
  $('#profileForm').classList.toggle('hidden',task!=='assessment');$('#knowledgeForm').classList.toggle('hidden',task!=='knowledge');
  $$('[data-task]').forEach(button=>button.setAttribute('aria-selected',String(button.dataset.task===task)));
  $('#activeFlow').innerHTML=task==='assessment'?'<b>Đánh giá hồ sơ</b><span>Validation → DL → Rules → Evidence → Explanation</span><small>Explanation Agent phản biện và kiểm chứng kết quả.</small>':'<b>Hỏi kiến thức</b><span>Hiểu câu hỏi → Retrieval → Explanation → phản biện</span><small>Không chạy DL. Thiếu nguồn thì tìm lại; thiếu thông tin thì hỏi thêm.</small>';
}
$$('[data-task]').forEach(button=>button.onclick=()=>setTask(button.dataset.task));
function prepareResults(task,comparison){$('#results').classList.toggle('solo',!comparison);$('#singleCard').hidden=!comparison;$('#resultTaskLabel').textContent=task==='assessment'?'Đánh giá hồ sơ · Validation → DL → Rules → Evidence → Explanation → Kiểm chứng':'Hỏi kiến thức · Hiểu câu hỏi → Retrieval → Explanation → phản biện';}
function runQuestion(payload){payload={...payload,task:payload.task||selectedTask};if(payload.task==='knowledge')payload.profile=null;prepareResults(payload.task,$('#compareSystems').checked);return $('#compareSystems').checked?runCompare(payload):runMultiFollowup(payload,true);}
function profile(){const f=new FormData(form),numeric=key=>String(f.get(key)??'').trim()===''?null:Number(f.get(key));return{gender:f.get('gender'),age:numeric('age'),bmi:numeric('bmi'),hbA1c_level:numeric('hbA1c_level'),blood_glucose_level:numeric('blood_glucose_level'),smoking_history:f.get('smoking_history'),hypertension:f.get('hypertension')?1:0,heart_disease:f.get('heart_disease')?1:0}}
$('#fillSample').onclick=()=>{const x={gender:'Male',age:67,bmi:34.6,hbA1c_level:7.2,blood_glucose_level:210,smoking_history:'former',hypertension:true,heart_disease:true};Object.entries(x).forEach(([k,v])=>{const el=form.elements[k];if(el.type==='checkbox')el.checked=v;else el.value=v});};
form.onsubmit=e=>{e.preventDefault();runQuestion({question:$('#question').value,profile:profile(),task:'assessment'})};
$('#knowledgeForm').onsubmit=e=>{e.preventDefault();runQuestion({question:$('#knowledgeQuestion').value,profile:null,task:'knowledge'})};
$$('[data-sample]').forEach(b=>b.onclick=()=>{setTask('knowledge');$('#knowledgeQuestion').value=samples[b.dataset.sample].question;runQuestion({...samples[b.dataset.sample],task:'knowledge'});});
async function runCompare(payload){
  if(requestBusy)return;setBusy(true);lastRequest=payload;
  $('#emptyState').classList.add('hidden');$('#results').classList.remove('hidden');
  $('#singleBody').innerHTML=loading();$('#multiBody').innerHTML=loading();$('#singleTrace').innerHTML='';$('#multiTrace').innerHTML='';
  document.querySelector('#compare').scrollIntoView({behavior:'smooth'});
  try{const r=await fetch('/api/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!r.ok)throw new Error((await r.json()).detail||'Request failed');
    const data=await r.json();render('single',data.single);render('multi',data.multi);
  }catch(e){$('#singleBody').innerHTML=`<div class="answer"><h3>Lỗi kết nối</h3><p>${escapeText(e.message)}</p></div>`;$('#multiBody').innerHTML='';}
  finally{setBusy(false);}
}
function loading(){return'<div class="answer"><span class="badge">processing</span><h3>Đang điều phối…</h3><p>Model và kho tri thức đang xử lý yêu cầu.</p></div>'}
function render(side,d){$(`#${side}Time`).textContent=`${d.total_duration_ms} ms`;const cites=d.knowledge?.citations||[];const risk=d.prediction?`<div class="risk"><strong>${(d.prediction.probability*100).toFixed(1)}%</strong><span>risk score<br>threshold ${(d.prediction.threshold*100).toFixed(1)}%</span></div>`:'';const stats=d.statistics?`<div class="risk"><strong>${d.statistics.rate}%</strong><span>${d.statistics.positive.toLocaleString()} / ${d.statistics.count.toLocaleString()}<br>${d.statistics.group}</span></div>`:'';const citations=cites.length?`<div class="citations">${cites.map(c=>`<a href="${c.url}" target="_blank">${c.title} ↗</a>`).join('')}</div>`:'';$(`#${side}Body`).innerHTML=`<div class="answer"><span class="badge">${label(d.status)}</span>${risk}${stats}<h3>${label(d.intent)}</h3>${renderAnswer(d)}${validation(d)}${citations}</div>`;$(`#${side}Trace`).innerHTML=d.traces.map((t,i)=>`<div class="trace-item"><i></i><span><b>${i+1}. ${t.agent}</b><small>${t.summary} · ${t.tool}</small></span><em>${t.duration_ms} ms</em></div>`).join('')}
function validation(d){return d.validation_errors?.length?`<div class="citations">${d.validation_errors.map(x=>`<a>${x.field}: ${x.message}</a>`).join('')}</div>`:''}
function label(x){
  const translations={knowledge:'Hỏi kiến thức',prediction:'Đánh giá hồ sơ',personal_guidance:'Hướng dẫn chung',
    statistics:'Thống kê',supported:'Có bằng chứng',supported_with_limitations:'Có bằng chứng, cần lưu ý',
    insufficient_evidence:'Bằng chứng chưa đủ',needs_clarification:'Cần làm rõ',validation_failed:'Hồ sơ chưa hợp lệ',out_of_scope:'Ngoài phạm vi',
    blocked_unsafe_request:'Yêu cầu bị chặn',human_review:'Cần xem xét thêm',partial:'Chưa hoàn tất',error:'Có lỗi'};
  return translations[x]||escapeText(String(x||'').replaceAll('_',' '));
}
const baseRender=render;
const escapeText=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function renderAnswer(d){
  const explanation=d.explanation;
  if(!explanation?.sections?.length)return `<p>${escapeText(d.answer)}</p>`;
  return `<div class="explanation-sections">${explanation.sections.map(section=>{
    const factors=section.id==='model_factors'?(explanation.model_factors||[]):[];
    const factorHtml=factors.length?`<div style="display:grid;gap:6px;margin-top:10px">${factors.map(f=>`<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;border-top:1px solid #e5e9e3;padding-top:7px"><span style="display:flex;flex-direction:column;font-size:10px"><b>${escapeText(f.label)}</b><small style="font-size:8px;color:#60736c">${escapeText(f.value)} · tham chiếu ${escapeText(f.baseline)}</small></span><strong style="font-size:10px;color:${f.impact>=0?'#d85a55':'#0f5b45'}">${f.impact>=0?'+':'−'}${Number(f.impact_percentage_points).toFixed(1)} đ.%</strong></div>`).join('')}</div>`:'';
    const sourceDetails=section.id==='medical_evidence'?renderEvidence(d):'';
    return `<section style="border:1px solid #d9ded8;border-radius:12px;padding:13px 14px;background:#faf9f4;margin-top:10px"><h4 style="font-size:12px;margin:0 0 6px">${escapeText(section.title)}</h4><p style="margin:0">${escapeText(section.text)}</p>${factorHtml}${sourceDetails}</section>`;
  }).join('')}</div>`;
}
function renderEvidence(d){
  const claims=d.explanation?.generation?.claims||[];
  const evidence=d.knowledge?.evidence||[];
  if(!evidence.length)return '';
  return `<details style="margin-top:12px"><summary>Nguồn và đoạn trích đã dùng (${evidence.length})</summary>${evidence.map(e=>{
    const s=e.source||{},claim=claims.find(c=>c.evidence_id===e.evidence_id);
    const url=/^https?:\/\//.test(s.url||'')?s.url+(s.page_start?'#page='+s.page_start:''):'';
    return `<article><p><b>${escapeText(s.source_file||s.title)}</b> ${s.page_start?'· trang PDF '+escapeText(s.page_start):'· '+escapeText(s.section||'bản tóm tắt nguồn')}<br><small>${escapeText(e.evidence_id)}</small></p><blockquote style="font-size:12px;white-space:pre-wrap">${escapeText(claim?.quote||e.text)}</blockquote>${url?`<a href="${escapeText(url)}" target="_blank" rel="noopener noreferrer">Mở nguồn ↗</a>`:''}</article>`;
  }).join('')}</details>`;
}
function renderGraphPaths(paths){
  if(!paths?.length)return '';
  return `<details><summary>Quan hệ từ Knowledge Graph</summary>${paths.map(edge=>{
    const url=/^https?:\/\//.test(edge.source_url||'')?edge.source_url+(edge.page?'#page='+edge.page:''):'';
    const source=`${escapeText(edge.evidence)}${edge.page?' · trang PDF '+escapeText(edge.page):''}`;
    return `<article><p>${escapeText(edge.subject)} → ${escapeText(edge.relation)} → ${escapeText(edge.object)}<br><small>${url?`<a href="${escapeText(url)}" target="_blank" rel="noopener noreferrer">${source} ↗</a>`:source}</small></p>${edge.quote?`<blockquote>${escapeText(edge.quote)}</blockquote>`:''}</article>`;
  }).join('')}</details>`;
}
render=function(side,d){
  baseRender(side,d);
  const peer=d.prediction?.second_opinion;
  const details=document.createElement('div');details.className='answer';
  details.innerHTML=`<h3>Thành phần đang chạy</h3><p>KB: <b>${escapeText(d.knowledge_backend)}</b> · Model: ${escapeText(d.prediction?.model||'Không gọi model')}</p>`+
    (d.explanation?.generation?`<p>Diễn giải: ${escapeText(d.explanation.generation.status)} · ${escapeText(d.explanation.generation.model||'template')}</p>`:'')+
    (d.knowledge?.retrieval?`<p><b>Vector RAG:</b> ${escapeText(d.knowledge.retrieval.backend)} · ${escapeText(d.knowledge.retrieval.embedding_model)}<br><small>${d.knowledge.retrieval.total_vectors||0} vectors · ${d.knowledge.retrieval.pdf_chunks||0} PDF chunks</small></p>`:'')+
    (peer?`<p>Đối chiếu ${escapeText(peer.model)}: ${(peer.probability*100).toFixed(1)}% · ngưỡng ${(peer.threshold*100).toFixed(1)}%</p>`:'')+
    (d.plan?`<p><b>Coordinator:</b> ${escapeText(label(d.plan.intent))} · ${escapeText(d.plan.goal)}</p><p><b>Truy vấn RAG:</b> ${(d.plan.queries||[]).map(escapeText).join(' / ')}</p>`:'')+
    (d.response_review?`<p><b>Critic:</b> ${escapeText(d.response_review.action)} · ${(d.response_review.reasons||[]).map(escapeText).join('; ')}</p>`:'')+
    (d.review?`<p><b>Critic:</b> ${escapeText(d.review.conclusion)}</p><p>${d.review.challenges.map(escapeText).join('<br>')}</p>`:'')+
    (d.revisions?.length?`<p><b>Các bước kiểm tra lại:</b> ${d.revisions.map(x=>escapeText(x.action)).join(' → ')}</p>`:'')+
    (d.workflow?`<p><b>Điều phối (${escapeText(d.workflow.controller||'policy đề xuất')}):</b> ${escapeText(d.workflow.action)}<br><small>Chỉ chọn bước xử lý; không lựa chọn điều trị.</small></p>`:'')+
    (d.messages?.length?`<details><summary>MessageBus — ${d.messages.length} thông điệp</summary>${d.messages.map(m=>`<p><b>${m.sequence}. ${escapeText(m.performative)}</b> ${escapeText(m.sender)} → ${escapeText(m.receiver)}</p>`).join('')}</details>`:'')+
    renderGraphPaths(d.knowledge?.paths);
  if(d.decision){details.insertAdjacentHTML('beforeend',`<h3>Kết luận sau phản biện</h3><p>${d.decision.review_required?'Tạm hoãn kết luận — cần xem xét thêm':['needs_clarification','validation_failed'].includes(d.status)?'Cần bổ sung hồ sơ':d.decision.final_label===1?'Nhãn mô hình: dương tính':d.decision.final_label===0?'Nhãn mô hình: âm tính':'Không đưa nhãn dự đoán'}</p><p>Lý do: ${(d.decision.reason_codes||[]).map(escapeText).join(', ')||'Không có yêu cầu xem xét'}</p>`);}
  if(d.verification){details.insertAdjacentHTML('beforeend',`<p><b>Verifier:</b> ${d.verification.passed?'Đạt kiểm tra nhất quán':'Chưa đạt'} · ${d.verification.issues.map(escapeText).join(', ')}</p>`);}
  if(d.revisions?.length){details.insertAdjacentHTML('beforeend',`<details><summary>Xem trạng thái trước / sau xử lý</summary>${d.revisions.map(r=>`<p><b>${escapeText(r.action)}</b></p><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${escapeText(JSON.stringify({before:r.before,after:r.after},null,2))}</pre>`).join('')}</details>`);}
  $(`#${side}Body`).appendChild(details);
  if(side==='multi'&&d.architecture_version==='conversation_v3')renderConversationForm(d);
  else if(side==='multi'&&d.clarification?.task==='testing_guidance')renderTestingForm(d);
};
function renderConversationForm(d){
  const request={...lastRequest},panel=document.createElement('form');panel.className='answer';
  const questions=d.clarification?.questions?.map(q=>q.text)||d.explanation?.followup_questions||[];
  panel.innerHTML=`<h3>${questions.length?'Bổ sung thông tin / hỏi tiếp':'Tiếp tục hội thoại'}</h3><p>Hệ thống giữ ngữ cảnh các lượt gần nhất trong phiên này.</p><textarea name="reply" maxlength="800" required placeholder="Nhập thông tin bổ sung hoặc câu hỏi tiếp theo"></textarea><button class="run" type="submit">Gửi câu trả lời →</button>`;
  panel.onsubmit=e=>{e.preventDefault();const history=[...(request.conversation||[]),{role:'user',content:request.question},{role:'assistant',content:d.answer.slice(0,3000)}].slice(-8);prepareResults('knowledge',false);runMultiFollowup({question:panel.elements.reply.value,profile:null,conversation:history,task:'knowledge'});};
  $('#multiBody').appendChild(panel);
}
async function runMultiFollowup(payload,initial=false){
  if(requestBusy)return;setBusy(true);
  if(initial){$('#emptyState').classList.add('hidden');$('#results').classList.remove('hidden');$('#singleTrace').innerHTML='';$('#singleTime').textContent='—';$('#singleBody').innerHTML='<div class="answer"><h3>Single-Agent chưa chạy</h3><p>Bật “So sánh thêm với Single-Agent” khi muốn chạy cả hai hệ.</p></div>';document.querySelector('#compare').scrollIntoView({behavior:'smooth'});}
  lastRequest=payload;$('#multiBody').innerHTML=loading();$('#multiTrace').innerHTML='';
  if(!initial&&!$('#singleHistoryNotice'))$('#singleBody').insertAdjacentHTML('afterbegin','<p id="singleHistoryNotice">Hội thoại tiếp theo chạy ở khung Multi-Agent; khung Single-Agent giữ trạng thái lượt đầu.</p>');
  try{const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,mode:'multi'})});
    if(!response.ok)throw Error('Không hoàn tất yêu cầu: HTTP '+response.status);
    render('multi',await response.json());
  }catch(error){$('#multiBody').innerHTML=`<div class="answer"><h3>Lỗi kết nối</h3><p>${escapeText(error.message)}</p></div>`;}
  finally{setBusy(false);}
}
function renderTestingForm(d){
  const request={...lastRequest},context=d.testing_context||{},panel=document.createElement('form');panel.className='answer';
  panel.innerHTML=`<h3>Bổ sung bối cảnh xét nghiệm</h3><label>Mục đích<select name="purpose" required><option value="">Chọn mục đích</option><option value="first_screening">Sàng lọc lần đầu</option><option value="repeat_abnormal">Kiểm tra lại kết quả bất thường</option><option value="followup">Theo dõi bệnh đã được chẩn đoán</option></select></label><label>Triệu chứng hoặc lý do muốn xét nghiệm<textarea name="symptoms" maxlength="500" required placeholder="Ghi không có nếu không có triệu chứng"></textarea></label><label>Kết quả xét nghiệm trước đó<textarea name="prior_results" maxlength="500" required placeholder="Ghi chưa xét nghiệm, hoặc tên xét nghiệm, kết quả, đơn vị và thời điểm"></textarea></label><button class="run" type="submit">Tiếp tục với thông tin này →</button><p>Thông tin chỉ đi kèm lượt hỏi này; không ghi vào KB dùng chung.</p>`;
  for(const key of ['purpose','symptoms','prior_results'])panel.elements[key].value=context[key]||'';
  panel.onsubmit=e=>{e.preventDefault();const data=new FormData(panel);runCompare({...request,testing_context:Object.fromEntries(data.entries())});};
  $('#multiBody').appendChild(panel);
}
fetch('/api/metadata').then(r=>r.json()).then(m=>{$('#metricRows').textContent=m.dataset.raw_rows.toLocaleString();$('#metricDocuments').textContent=m.vector_retrieval?.total_vectors||m.knowledge_documents;$('#metricF1').textContent=m.pytorch.test.f1.toFixed(3);$('#metricF1').nextElementSibling.textContent='F1 test PyTorch đang chạy';$('.status').textContent=`${m.active_model} · KB ${m.knowledge_backend}`}).catch(()=>{});
