const path=require('path');
const {chromium}=require('C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:8010/',{timeout:60000});
  await page.locator('#question').fill('Tôi đi xét nghiệm gì bây giờ?');
  const firstPromise=page.waitForResponse(r=>r.url().endsWith('/api/compare'));
  await page.locator('#profileForm button[type="submit"]').click();
  const first=await (await firstPromise).json();
  if(first.multi.status!=='needs_clarification'||first.multi.prediction!==null)throw Error('Personal testing question did not clarify');
  const followup=page.locator('#multiBody form');await followup.waitFor();
  await followup.locator('[name="purpose"]').selectOption('first_screening');
  await followup.locator('[name="symptoms"]').fill('Không có triệu chứng, muốn sàng lọc lần đầu');
  await followup.locator('[name="prior_results"]').fill('Chưa xét nghiệm');
  const nextPromise=page.waitForResponse(r=>r.url().endsWith('/api/compare'),{timeout:150000});
  await followup.locator('button[type="submit"]').click();
  const nextResponse=await nextPromise;const next=await nextResponse.json();
  if(!nextResponse.ok()||next.multi.clarification||next.multi.prediction!==null||!next.multi.verification.passed)throw Error('Clarification continuation failed');
  if(next.multi.testing_context.purpose!=='first_screening')throw Error('Context was lost');
  await page.screenshot({path:path.resolve('tmp/testing_guidance_demo.png'),fullPage:true});
  console.log(JSON.stringify({first_status:first.multi.status,next_status:next.multi.status,
   next_generation:next.multi.explanation.generation?.status,verification:next.multi.verification.passed,
   answer:next.multi.answer,sources:next.multi.knowledge?.citations?.map(c=>({title:c.title,page:c.page})),errors}));
  if(errors.length)throw Error('Browser errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1)});
