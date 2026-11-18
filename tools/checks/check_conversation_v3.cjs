// Browser integration for the generic conversation form. Real API responses;
// no mock agents and no synthetic medical source is inserted into the KB.
const path=require('path');
const {chromium}=require('C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:8010/',{timeout:60000});
  await page.locator('label').filter({has:page.locator('#compareSystems')}).click();
  await page.locator('#knowledgeTab').click();
  await page.locator('#knowledgeQuestion').fill('Tôi đi xét nghiệm gì bây giờ?');
  const firstPromise=page.waitForResponse(r=>r.url().endsWith('/api/compare'),{timeout:240000});
  await page.locator('#knowledgeForm button[type="submit"]').click();
  const first=await (await firstPromise).json();
  if(first.multi.architecture_version!=='conversation_v3')throw Error('Wrong default architecture');
  if(first.multi.prediction)throw Error('Knowledge question unexpectedly triggered model');
  const form=page.locator('#multiBody form');await form.waitFor();
  const reply='Tôi chưa từng được chẩn đoán, chưa xét nghiệm, không có triệu chứng; muốn tìm hiểu sàng lọc lần đầu.';
  await form.locator('[name="reply"]').fill(reply);
  const nextPromise=page.waitForResponse(r=>r.url().endsWith('/api/run'),{timeout:240000});
  await form.locator('button').click();
  const response=await nextPromise,request=response.request().postDataJSON(),next=await response.json();
  if(request.conversation?.length!==2||request.question!==reply)throw Error('Conversation context was not sent');
  if(next.prediction)throw Error('Follow-up unexpectedly triggered prediction');
  await page.screenshot({path:path.resolve('tmp/conversation_v3_demo.png'),fullPage:true});
  console.log(JSON.stringify({first_status:first.multi.status,next_status:next.status,
    architecture:next.architecture_version,history_messages:request.conversation.length,
    answer:next.answer,critic:next.response_review?.action,
    sources:next.knowledge?.citations?.map(c=>({title:c.title,page:c.page_start})),errors}));
  if(errors.length)throw Error('Browser JavaScript errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1)});
