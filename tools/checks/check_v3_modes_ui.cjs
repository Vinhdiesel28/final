// UI contract replay only; live inference/retrieval is measured by the Python benchmark.
const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),calls=[],errors=[],legacy=[];
 const report=JSON.parse(fs.readFileSync('results/benchmark_v3.json','utf8'));
 const knowledge=report.trials.find(r=>r.kind==='knowledge').response,assessment=report.trials.find(r=>r.kind==='assessment').response;
 page.on('pageerror',error=>errors.push(error.message));
 page.on('request',request=>{if(/\/api\/benchmark(?:$|\/diabetes|\/critic|\/corpus)/.test(request.url()))legacy.push(request.url());});
 await page.route('**/api/run',async route=>{const payload=route.request().postDataJSON();calls.push(payload);await route.fulfill({json:payload.task==='assessment'?assessment:knowledge});});
 try{
  await page.goto('http://127.0.0.1:8010/',{timeout:60000});
  await page.locator('#v3Benchmark h3').first().waitFor({timeout:30000});
  if(!await page.locator('#profileForm').isVisible()||await page.locator('#knowledgeForm').isVisible())throw Error('Wrong initial task panel');
  await page.locator('#profileForm button[type=submit]').click();await page.waitForFunction(()=>!requestBusy);
  if(calls[0].task!=='assessment'||!calls[0].profile?.hbA1c_level)throw Error('Assessment payload missing profile/task');
  await page.locator('#profileForm [name=age]').fill('');
  if(await page.evaluate(()=>profile().age)!==null)throw Error('Empty age must not silently become zero');
  if(!await page.locator('#singleCard').isHidden())throw Error('Single baseline should be hidden by default');
  await page.locator('#knowledgeTab').click();
  if(await page.locator('#profileForm').isVisible()||!await page.locator('#knowledgeForm').isVisible())throw Error('Knowledge panel did not switch');
  await page.locator('#knowledgeQuestion').fill('HbA1c là gì?');
  await page.locator('#knowledgeForm button[type=submit]').click();await page.waitForFunction(()=>!requestBusy);
  if(calls[1].task!=='knowledge'||calls[1].profile!==null)throw Error('Knowledge leaked profile or wrong task');
  if(!await page.locator('#resultTaskLabel').innerText().then(t=>t.includes('Hỏi kiến thức')))throw Error('Result flow label wrong');
  if(await page.locator('#singleBench,#multiBench,#diabetesBenchmark,#criticBenchmark').count())throw Error('Old benchmark remains in DOM');
  if(legacy.length)throw Error('Old benchmark API still fetched');
  await page.screenshot({path:path.resolve('tmp/v3_modes_desktop.png'),fullPage:true});
  await page.locator('#assessment').screenshot({path:path.resolve('tmp/v3_task_panel.png')});
  await page.locator('#v3Benchmark .v3-panel').first().screenshot({path:path.resolve('tmp/v3_benchmark_header.png')});
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2))throw Error('Mobile horizontal overflow');
  await page.screenshot({path:path.resolve('tmp/v3_modes_mobile.png'),fullPage:true});
  await page.locator('#assessment').screenshot({path:path.resolve('tmp/v3_task_mobile.png')});
  if(errors.length)throw Error(errors.join('; '));
  console.log(JSON.stringify({scope:'UI replay; actual benchmark API',tasks:calls.map(r=>r.task),knowledge_profile:calls[1].profile,legacy_requests:legacy.length,errors}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exit(1)});
