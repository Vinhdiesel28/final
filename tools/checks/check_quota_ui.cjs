// UI contract check with a recorded response. Does not measure LLM quality.
const fs=require('fs');
const {chromium}=require('C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage(),errors=[],calls=[];
 const recorded=JSON.parse(fs.readFileSync('results/conversation_v3_case1.json','utf8')).response;
 page.on('pageerror',e=>errors.push(e.message));
 let release,arrive;
 const arrived=new Promise(r=>arrive=r),gate=new Promise(r=>release=r);
 await page.route('**/api/run',async route=>{calls.push({endpoint:'run',body:route.request().postDataJSON()});arrive();await gate;await route.fulfill({json:recorded});});
 await page.route('**/api/compare',async route=>{calls.push({endpoint:'compare',body:route.request().postDataJSON()});await route.fulfill({json:{single:recorded,multi:recorded}});});
 try{
  await page.goto('http://127.0.0.1:8010/');
  if(await page.locator('#compareSystems').isChecked())throw Error('Comparison should be opt-in');
  await page.locator('#question').fill('HbA1c là gì?');
  await page.locator('#profileForm button[type="submit"]').click();await arrived;
  if(!await page.locator('#profileForm button[type="submit"]').isDisabled())throw Error('Submit remains enabled during request');
  await page.evaluate(()=>runQuestion({question:'Duplicate request'}));
  if(calls.length!==1)throw Error('Duplicate request was sent');
  release();await page.waitForFunction(()=>!requestBusy);
  if(calls[0].endpoint!=='run'||calls[0].body.mode!=='multi')throw Error('Default request unnecessarily compares');
  await page.locator('label').filter({has:page.locator('#compareSystems')}).click();
  await page.locator('#profileForm button[type="submit"]').click();await page.waitForFunction(()=>!requestBusy);
  if(calls[1]?.endpoint!=='compare')throw Error('Opt-in comparison stopped working');
  if(errors.length)throw Error(errors.join('; '));
  console.log(JSON.stringify({scope:'UI replay only',default_endpoint:calls[0].endpoint,comparison_endpoint:calls[1].endpoint,duplicate_blocked:true,errors}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exit(1)});
