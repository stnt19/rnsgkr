"""Cross-check OCR with exact embedded glyph outlines, never guessed offsets.

Only Identity-H fonts without ToUnicode are repaired. A character is recovered
only when its embedded outline equals the same glyph in an installed font.
Off-page hidden text is excluded using PDFium character rectangles.
"""
import argparse
import ctypes
import hashlib
import io
import json
from functools import lru_cache
from pathlib import Path
from fontTools.ttLib import TTCollection, TTFont
from pypdf import PdfReader
import pypdfium2 as pdfium
import pypdfium2.raw as raw

ROOT=Path(__file__).resolve().parents[1]


class GlyphChecker:
    def __init__(self,pdf_path,font_path):
        self.reader=PdfReader(pdf_path)
        self.system={f['name'].getDebugName(1):f for f in TTCollection(str(font_path)).fonts}
        self.fonts={}
        self.pdf=pdfium.PdfDocument(str(pdf_path))

    def register(self,page):
        resources=page.get('/Resources',{})
        if hasattr(resources,'get_object'):resources=resources.get_object()
        for ref in resources.get('/Font',{}).values():
            font=ref.get_object();name=str(font.get('/BaseFont','')).lstrip('/')
            if name in self.fonts:continue
            self.fonts[name]=None
            family=name.split('+')[-1].split('-')[0]
            if family not in self.system or font.get('/Encoding')!='/Identity-H' or '/ToUnicode' in font:continue
            descendant=font['/DescendantFonts'][0].get_object()
            if descendant.get('/CIDToGIDMap')!='/Identity':continue
            data=descendant['/FontDescriptor'].get('/FontFile2')
            if not data:continue
            embedded=TTFont(io.BytesIO(data.get_object().get_data()))
            system=self.system[family];reverse={}
            for cp,g in system.getBestCmap().items():
                reverse.setdefault(system.getGlyphID(g),set()).add(chr(cp))
            self.fonts[name]=(embedded,system,reverse)

    @lru_cache(maxsize=50000)
    def decode(self,name,code):
        spec=self.fonts.get(name)
        if not spec:return None
        embedded,system,reverse=spec
        options=reverse.get(code,set())
        if len(options)!=1:return None
        try:
            a=embedded['glyf'][embedded.getGlyphName(code)].getCoordinates(embedded['glyf'])
            b=system['glyf'][system.getGlyphName(code)].getCoordinates(system['glyf'])
        except (KeyError,IndexError):return None
        return next(iter(options)) if a==b else None

    def page(self,number):
        self.register(self.reader.pages[number-1])
        page=self.pdf[number-1];tp=page.get_textpage();width,height=page.get_size()
        text=[];checked=0;unknown=0;hidden=0
        for i in range(tp.count_chars()):
            code=raw.FPDFText_GetUnicode(tp,i)
            if code in (10,13):text.append(chr(code));continue
            x0,y0,x1,y1=tp.get_charbox(i)
            if x1<0 or x0>width or y1<0 or y0>height:hidden+=1;continue
            flags=ctypes.c_int();size=raw.FPDFText_GetFontInfo(tp,i,None,0,ctypes.byref(flags))
            buffer=ctypes.create_string_buffer(size)
            raw.FPDFText_GetFontInfo(tp,i,buffer,size,ctypes.byref(flags))
            name=buffer.value.decode('utf-8',errors='replace')
            char=self.decode(name,code)
            if char is None:
                # PDFium-generated spaces have no font; only literal whitespace survives.
                if chr(code).isspace():text.append(chr(code))
                else:unknown+=1;text.append('\ufffd')
            else:checked+=1;text.append(char)
        tp.close();page.close()
        return {'text':''.join(text).replace('\r','').strip(),'checkedCharacters':checked,'unmappedCharacters':unknown,'hiddenCharacters':hidden}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pages');parser.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/gulim.ttc'));args=parser.parse_args()
    doc=next(d for d in json.loads((ROOT/'data/manuals.local.json').read_text(encoding='utf-8')) if d['id']=='wiring')
    digest=hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()
    if digest!=doc['sha256']:raise ValueError('Original PDF changed')
    checker=GlyphChecker(doc['path'],args.font)
    pages=list(map(int,args.pages.split(','))) if args.pages else range(1,doc['pages']+1)
    result=[]
    for n in pages:
        result.append({'page':n,**checker.page(n)})
        if n%50==0:print('Glyph comparison',n,flush=True)
    checker.pdf.close()
    output={'sourceHash':digest,'systemFontHash':hashlib.sha256(args.font.read_bytes()).hexdigest(),'method':'exact-glyph-outline','pages':result}
    name='wiring-ocr-glyphs.local.json' if not args.pages else 'wiring-ocr-glyph-pilot.local.json'
    (ROOT/'data'/name).write_text(json.dumps(output,ensure_ascii=False),encoding='utf-8')
    print('Checked',len(result),'pages',flush=True)


if __name__=='__main__':main()
