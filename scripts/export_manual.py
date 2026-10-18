"""Export only the public in-game manual; no live game calls or save writes.

Offline page reconstruction, not a claim of pixel-identical Unity screenshots.
Requires the existing optional UnityPy analysis environment.
"""
import gc
import hashlib
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import UnityPy

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'.robotomy/runtime/LobotomyCorp/LobotomyCorp_Data'
OUT=Path(r'D:\Projects\Robotomy_Player\Manual')


def run():
    OUT.mkdir(exist_ok=True)
    env=UnityPy.load(str(DATA/'globalgamemanagers'))
    manager=next(o for o in env.objects if o.type.name=='ResourceManager')
    mapping=manager.read_typetree()['m_Container']
    external={i+1:Path(v.path).name for i,v in enumerate(manager.assets_file.externals)}
    del manager,env;gc.collect()
    env=UnityPy.load(str(DATA/'resources.assets'))
    xml=next(o for o in env.objects if o.type.name=='TextAsset' and o.peek_name()=='ManualStructure').read().m_Script
    if isinstance(xml,bytes):xml=xml.decode('utf8')
    structure=ET.fromstring(xml)
    del env;gc.collect()
    local={e.get('id'):''.join(e.itertext()) for e in ET.parse(DATA/'ExternalData/xml/Language/Localize/kr/ManualDesc_kr.xml').getroot()}
    nodes=[]
    for main in structure.findall('main'):
        for sub in main.findall('sub'):
            for node in sub.findall('node') or [sub]:
                nodes.append((main,sub,node))
    required={n.get('sprite') for _,_,n in nodes}
    pictures={}
    for fileid in sorted(set(v['m_FileID'] for k,v in mapping if k.startswith('sprites/ui/manual/kr/'))):
        env=UnityPy.load(str(DATA/external[fileid]));objects={o.path_id:o for o in env.objects}
        for key,ref in mapping:
            if ref['m_FileID']!=fileid or not key.startswith('sprites/ui/manual/kr/'):continue
            sprite=key.rsplit('/',1)[1]
            if sprite not in required:continue
            obj=objects[ref['m_PathID']]
            if obj.type.name!='Sprite':continue
            im=obj.read().image
            filename=f'background-{sprite}.png';im.save(OUT/filename)
            pictures[sprite]=(filename,im.size)
        del objects,env;gc.collect()
    assert required==set(pictures), 'Missing manual sprite'
    index=['# 게임 내 매뉴얼 — 한국어 56쪽\n',
           '게임에서 누구나 열람할 수 있는 매뉴얼의 오프라인 사본입니다. 게임 조작 없이 필요한 쪽을 읽을 수 있습니다.\n',
           '**PNG는 원본 그림과 한국어 표시 문구를 배치한 오프라인 재구성입니다. 실제 게임 화면 캡처가 아니며 글꼴·줄바꿈은 다를 수 있습니다.** 각 Markdown에는 같은 페이지의 표시 문구 전체가 있습니다.\n',
           '필요한 페이지의 Markdown으로 읽고, 도식·위치가 필요하면 PNG를 확인하세요. 파일 제공은 읽었다는 뜻이 아닙니다. 실제로 읽은 쪽을 기존 경험 기록 도구에 페이지 번호와 함께 남기고, 플레이로 확인한 사실과 매뉴얼 설명을 구분하세요.\n']
    manifest=[]
    def text(identifier):
        assert identifier in local, f'Missing localized manual string {identifier}'
        return local[identifier]
    def markup(value):
        value=html.escape(value)
        value=re.sub(r'&lt;color=(#[0-9A-Fa-f]{6,8})&gt;',r'<span style="color:\1">',value)
        value=value.replace('&lt;/color&gt;','</span>')
        for tag in ('b','i'):value=value.replace(f'&lt;{tag}&gt;',f'<{tag}>').replace(f'&lt;/{tag}&gt;',f'</{tag}>')
        return value
    for number,(main,sub,node) in enumerate(nodes,1):
        title=' / '.join([text('Manual_MainCategory_'+main.get('id')),text('Manual_SubCategory_'+sub.get('id'))]+([text('Manual_Node_'+node.get('id'))] if node.tag=='node' else []))
        bg,(width,height)=pictures[node.get('sprite')];scale=width/3248
        elements=[];plain=[]
        def box(x,y,w,h,size,value):
            elements.append(f'<div class="box" style="left:{x*scale}px;top:{y*scale}px;width:{w*scale}px;height:{h*scale}px;font-size:{size*scale}px">{markup(value)}</div>')
            plain.append(value)
        for item in node:
            if item.tag=='text':
                box(float(item.get('x',0)),-float(item.get('y',0)),float(item.get('w',0)),float(item.get('h',0)),float(item.get('size',50)),text('Manual_Text_'+item.text.strip()))
            elif item.tag=='list':
                y=-float(item.get('y',0))
                for i,child in enumerate(item.findall('text'),1):
                    h=float(child.get('h',item.get('height',120)))
                    value=text('Manual_Text_'+child.text.strip())
                    prefix=item.get('prefix','')
                    if prefix=='arrow':value='▶ '+value
                    elif prefix=='numeric':value=f'{i}. '+value
                    box(float(item.get('x',0)),y,float(item.get('w',0)),h,float(item.get('size',50)),value)
                    y+=h+float(item.get('space',0))
        name=f'{number:02d}'
        page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:black;color:#ffffaa;font-family:"Malgun Gothic",sans-serif}}#page{{position:relative;width:{width}px;height:{height}px;background:black url("{bg}") no-repeat;background-size:100% 100%}}.box{{position:absolute;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.25;font-weight:600}}</style>
<div id="page">{''.join(elements)}</div></html>'''
        (OUT/f'{name}.html').write_text(page,encoding='utf8')
        md=f'# {number:02d}. {title}\n\n출처: 게임 내 한국어 매뉴얼. 오프라인 재구성으로 실제 플레이 캡처와 구분합니다.\n\n![페이지 그림]({name}.png)\n\n## 표시 문구 전체\n\n'+'\n\n'.join('> '+s.replace('\n','\n> ') for s in plain)+'\n'
        (OUT/f'{name}.md').write_text(md,encoding='utf8')
        index.append(f'- [{number:02d}. {title}]({name}.md) · [이미지]({name}.png)\n')
        manifest.append({'page':number,'title':title,'html':f'{name}.html','image':f'{name}.png','text':f'{name}.md','width':width,'height':height,'text_blocks':len(plain)})
    (OUT/'README.md').write_text('\n'.join(index),encoding='utf8')
    (OUT/'manifest.json').write_text(json.dumps({'kind':'offline_reconstruction_of_ingame_manual','pages':manifest},ensure_ascii=False,indent=2),encoding='utf8')
    (ROOT/'.robotomy/analysis/manual-export-provenance.json').write_text(json.dumps({'structure_sha256':hashlib.sha256(xml.encode()).hexdigest(),'page_count':len(nodes),'output':str(OUT),'source':'private runtime manual only; game/saves unchanged'},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'pages':len(nodes),'output':str(OUT)},ensure_ascii=False))


if __name__=='__main__':run()
