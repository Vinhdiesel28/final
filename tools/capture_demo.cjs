const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8010/');
 await page.locator('#fillSample').click();
 const result=page.waitForResponse(r=>r.url().endsWith('/api/compare'));
 await page.locator('#profileForm button[type="submit"]').click();
 const response=await result;const data=await response.json();
 if(!response.ok()||data.multi.knowledge_backend!=='neo4j'||!data.multi.messages.length)throw Error('Demo failed');
 if(JSON.stringify(data.single.prediction)!==JSON.stringify(data.multi.prediction))throw Error('Prediction mismatch');
 await page.locator('#multiBody details').first().waitFor();
 await page.screenshot({path:path.resolve('report/assets/demo_neo4j_pytorch.png'),fullPage:true});
 console.log(JSON.stringify({backend:data.multi.knowledge_backend,model:data.multi.prediction.model,messages:data.multi.messages.length,errors}));
 await browser.close();if(errors.length)process.exit(1);
})().catch(e=>{console.error(e);process.exit(1)});
