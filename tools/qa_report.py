from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
pdf=ROOT/'report/project01_CT_08_934_NguyenMinhVinh.pdf'
reader=PdfReader(pdf)
print('Pages:',len(reader.pages))
for i,p in enumerate(reader.pages,1):
    text=p.extract_text() or ''
    print(i,len(text),text[:65].replace('\n',' '))
imgs=sorted((ROOT/'tmp/project_v2_render').glob('page-*.png'))
for first in range(0,len(imgs),6):
    sheet=Image.new('RGB',(1200,1800),'#ddd');d=ImageDraw.Draw(sheet)
    for j,path in enumerate(imgs[first:first+6]):
        im=Image.open(path);im.thumbnail((580,550))
        x=(j%2)*600;y=(j//2)*600
        sheet.paste(im,(x,y+28));d.text((x+10,y+7),path.stem,fill='black')
    sheet.save(ROOT/f'tmp/project_v2_render/contact-{first//6+1}.png')
