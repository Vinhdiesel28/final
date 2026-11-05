from pathlib import Path
import sys,json
from pypdf import PdfReader
from PIL import Image,ImageDraw
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'tmp/final_continued_render'
reader=PdfReader(ROOT/'report/tieuluan_final_CT_08_934_NguyenMinhVinh.pdf')
print('Pages',len(reader.pages))
for i,p in enumerate(reader.pages,1):
    t=p.extract_text() or ''
    if t.strip().startswith(f'{i} \nCHƯƠNG') or i>=57:print(i,len(t),t[:100].replace('\n',' '))
imgs=sorted(folder.glob('page-*.png'))[:len(reader.pages)]
for start in range(0,len(imgs),6):
    canvas=Image.new('RGB',(1200,1800),'#ddd');draw=ImageDraw.Draw(canvas)
    for j,path in enumerate(imgs[start:start+6]):
        im=Image.open(path);im.thumbnail((580,550));x=j%2*600;y=j//2*600
        canvas.paste(im,(x,y+28));draw.text((x+8,y+8),path.stem,fill='black')
    canvas.save(folder/f'contact-{start//6+1}.png')
