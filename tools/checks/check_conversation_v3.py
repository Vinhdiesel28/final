"""Small live integration check, not a medical benchmark or comparative evaluation."""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request,urlopen
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
QUESTIONS=['A1C phản ánh điều gì?', 'Tôi đi xét nghiệm gì bây giờ?',
           'Theo IDF, mục tiêu HbA1c có cần cá nhân hóa theo nguy cơ hạ đường huyết không?',
           'Nghiên cứu ZXQ9992026 chưa công bố cho kết quả chính xác là gì?',
           'Tôi 30 tuổi, không có triệu chứng, chưa từng xét nghiệm hoặc được chẩn đoán, chỉ muốn tìm hiểu sàng lọc lần đầu.']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',type=int,choices=range(1,6),required=True)
    parser.add_argument('--direct',action='store_true')
    args=parser.parse_args();question=QUESTIONS[args.case-1]
    bundle=json.loads((ROOT/'knowledge/hybrid/kb_bundle.json').read_text(encoding='utf-8'))
    chunks={c['id']:c for c in bundle['chunks']};docs={d['id']:d for d in bundle['documents']}
    history=[{'role':'user','content':'Tôi đi xét nghiệm gì bây giờ?'},{'role':'assistant','content':'Bạn đã xét nghiệm hoặc được chẩn đoán chưa? Có triệu chứng gì và bao nhiêu tuổi?'}] if args.case==5 else []
    request=Request('http://127.0.0.1:8010/api/run',data=json.dumps({'question':question,'mode':'multi','conversation':history}).encode(),headers={'Content-Type':'application/json'})
    started=time.perf_counter()
    if args.direct:
        import sys
        sys.path.insert(0,str(ROOT/'src'))
        from agent_system import MultiAgent,Services
        result=MultiAgent(Services()).run(question,conversation=history)
    else:
        with urlopen(request,timeout=240) as response:result=json.load(response)
    checks=[]
    for claim in (result.get('explanation') or {}).get('generation',{}).get('claims',[]):
        chunk=chunks.get(claim['evidence_id']);quote=claim['quote']
        check={'chunk_id':claim['evidence_id'],'quote_in_chunk':bool(chunk and quote in chunk['text'])}
        if chunk and chunk['source_type']=='pdf':
            page=PdfReader(ROOT/docs[chunk['document_id']]['local_path']).pages[chunk['page_start']-1].extract_text() or ''
            check['quote_in_pdf_page']=' '.join(quote.split()) in ' '.join(page.split())
        checks.append(check)
    report={'scope':'Live integration, no ground-truth medical evaluation','question':question,'elapsed_seconds':round(time.perf_counter()-started,2),'source_checks':checks,'response':result}
    (ROOT/f'results/conversation_v3_case{args.case}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('question','elapsed_seconds','source_checks')},ensure_ascii=True))
    print(json.dumps({k:result.get(k) for k in ('status','answer','plan','response_review','verification','revisions')},ensure_ascii=True))

if __name__=='__main__':main()
