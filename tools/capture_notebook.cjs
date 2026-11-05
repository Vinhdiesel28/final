// Browser screenshots of executed notebook code and outputs, split into page-safe panels.
const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'..');
const nb=JSON.parse(fs.readFileSync(path.join(root,process.argv[2]||'notebooks/08_project_ml_neo4j_multiagent.ipynb'),'utf8'));
const out=path.join(root,process.argv[3]||'report/assets/notebook');fs.mkdirSync(out,{recursive:true});
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1100,height:1400},deviceScaleFactor:1.5});
 let n=0;
 for(const cell of nb.cells){
  if(cell.cell_type!=='code')continue;n++;
  let outputs='';
  for(const o of cell.outputs||[]){
   if(o.output_type==='error')throw Error(o.evalue);
   const html=o.data?.['text/html']; const plain=o.text||o.data?.['text/plain'];
   if(html)outputs+=Array.isArray(html)?html.join(''):html;
   else if(plain)outputs+='<pre>'+esc(Array.isArray(plain)?plain.join(''):plain)+'</pre>';
  }
  const source=Array.isArray(cell.source)?cell.source.join(''):cell.source;
  if(process.argv[3]?.endsWith('/training')){
    for(const file of fs.readdirSync(out))if(/^cell-01-\d+\.png$/.test(file))fs.unlinkSync(path.join(out,file));
    const plainOutput=(cell.outputs||[]).map(o=>Array.isArray(o.text)?o.text.join(''):o.text||'').join('');
    let part=0;
    for(const [label,text] of [['Code',source],['Output',plainOutput]]){
      const lines=text.trimEnd().split('\n');
      for(let start=0;start<lines.length;){
        const end=lines.length-(start+30)<=5?lines.length:start+30;
        part++;
        await page.setContent(`<meta charset="utf-8"><style>body{margin:20px;color:#111;background:white}section{padding:20px;border:1px solid #888}h3{font:18px Arial}pre{font:17px/1.45 Consolas;white-space:pre-wrap;overflow-wrap:anywhere}</style><section><h3>In [${cell.execution_count}] — ${label} — dòng ${start+1} đến ${end}</h3><pre>${esc(lines.slice(start,end).join('\n'))}</pre></section>`);
        await page.locator('section').screenshot({path:path.join(out,`cell-01-${part}.png`)});
        start=end;
      }
    }
    continue;
  }
  const html=`<meta charset="utf-8"><style>body{margin:0;padding:20px;background:white;color:#111;font:17px Arial}section{border:1px solid #888;padding:18px}pre{font:17px/1.45 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;text-align:left}table{border-collapse:collapse;font:15px/1.4 Arial;margin:16px 0;width:100%}td,th{border:1px solid #aaa;padding:6px;text-align:left;overflow-wrap:anywhere}h3{font-size:18px}.output{border-top:1px solid #aaa;padding-top:10px}</style><section><h3>In [${cell.execution_count}] — Cell ${n}</h3><pre>${esc(source)}</pre><div class="output"><h3>Output</h3>${outputs}</div></section>`;
  fs.writeFileSync(path.join(out,`cell-${String(n).padStart(2,'0')}.html`),html);
  await page.setContent(html);await page.evaluate(()=>document.fonts.ready);
  const height=Math.ceil((await page.locator('section').boundingBox()).height+40);
  await page.setViewportSize({width:1100,height:Math.max(1400,height)});
  for(const file of fs.readdirSync(out))if(file.startsWith(`cell-${String(n).padStart(2,'0')}-`)&&file.endsWith('.png'))fs.unlinkSync(path.join(out,file));
  for(let y=0,part=1;y<height;part++){
    const slice=Math.min(1250,height-y);
    await page.screenshot({path:path.join(out,`cell-${String(n).padStart(2,'0')}-${part}.png`),clip:{x:0,y,width:1100,height:slice},captureBeyondViewport:true});
    if(y+slice>=height)break;
    y+=1220; // Small overlap preserves lines at screenshot boundaries.
  }
 }
 await browser.close();console.log(`Captured ${n} executed cells`);
})().catch(e=>{console.error(e);process.exit(1)});
