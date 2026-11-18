"""Exercise the running app and verify generated source quotes against raw PDFs/HTML."""
import argparse
import json
import re
import time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import URLError
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
def normalized(text):return ' '.join(text.split())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',type=int,choices=range(1,5));args=parser.parse_args()
    for attempt in range(30):
        try:
            with urlopen('http://127.0.0.1:8010/health',timeout=2) as response:json.load(response)
            break
        except URLError:
            if attempt==29:raise
            time.sleep(1)
    bundle=json.loads((ROOT/'knowledge/hybrid/kb_bundle.json').read_text(encoding='utf-8'))
    by_id={c['id']:c for c in bundle['chunks']};docs={d['id']:d for d in bundle['documents']}
    tests=['A1C phản ánh điều gì?',
           'Theo IDF, hoạt động thể lực ảnh hưởng đến độ nhạy insulin như thế nào?',
           'What does the IDF guideline say about HbA1c targets and hypoglycaemia?',
           'Thử nghiệm ZXQ9992026 chưa công bố có kết quả chính xác là gì?']
    if args.case:tests=[tests[args.case-1]]
    results=[]
    for question in tests:
        body=json.dumps({'question':question,'mode':'multi'}).encode()
        request=Request('http://127.0.0.1:8010/api/run',data=body,headers={'Content-Type':'application/json'})
        started=time.perf_counter()
        with urlopen(request,timeout=150) as response:result=json.load(response)
        generation=(result.get('explanation') or {}).get('generation',{})
        checks=[]
        for claim in generation.get('claims',[]):
            source=by_id.get(claim.get('evidence_id'));quote=claim.get('quote','')
            check={'evidence_id':claim.get('evidence_id'),'valid_chunk':bool(source),
                   'quote_in_chunk':bool(source and quote in source['text'])}
            if source:
                document=docs[source['document_id']]
                check.update({'source_type':source['source_type'],'title':source['title'],'page':source.get('page_start'),'section':source.get('section'),'url':source['url']})
                if source['source_type']=='pdf':
                    reader=PdfReader(ROOT/document['local_path'])
                    page=reader.pages[source['page_start']-1].extract_text() or ''
                    check['quote_in_original_pdf_page']=normalized(quote) in normalized(page)
                elif source['source_type']=='web':
                    from html import unescape
                    html=(ROOT/document['local_path']).read_text(encoding='utf-8')
                    raw=unescape(re.sub('<[^>]+>',' ',html))
                    check['quote_in_html_snapshot']=normalized(quote) in normalized(raw)
            checks.append(check)
        results.append({'question':question,'status':result['status'],'generation':generation,'answer':result['answer'],
                        'verification':result['verification'],'citations':(result.get('knowledge') or {}).get('citations',[]),
                        'source_checks':checks,'elapsed_seconds':round(time.perf_counter()-started,2)})
        print(json.dumps({'question':question,'status':result['status'],'generation':generation.get('status'),'http_status':generation.get('http_status'),'source_checks':checks},ensure_ascii=True),flush=True)
    report={'scope':'Four live demo checks, not a medical quality benchmark','results':results}
    filename=f'live_groq_citation_check_case{args.case}.json' if args.case else 'live_groq_citation_check.json'
    (ROOT/'results'/filename).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
