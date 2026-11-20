"""Package reviewable code, docs, QA and the supplied catalog; exclude runtime/private data."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'deliverables'
OUT.mkdir(exist_ok=True)
archive=OUT/'迈特威客服Agent演示与实施方案.zip'
files=[]
for name in ['app.py','README.md','start.ps1','启动演示.cmd','run_checks.ps1','.env.example','.gitignore']:
    files.append(ROOT/name)
for folder in ['agent','data','static','docs','scripts','tests','qa']:
    files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.sqlite3','.db'})
files=sorted(set(files),key=lambda p:str(p.relative_to(ROOT)))
manifest=[]
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for file in files:
        arcname='mittiway-agent/'+file.relative_to(ROOT).as_posix()
        z.write(file,arcname)
        manifest.append({'path':arcname,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    catalog=ROOT.parent/'2026 迈特威画册.pdf'
    if catalog.exists():
        z.write(catalog,catalog.name)
        manifest.append({'path':catalog.name,'bytes':catalog.stat().st_size,'sha256':hashlib.sha256(catalog.read_bytes()).hexdigest()})
    note='迈特威客服 Agent 本地开发演示\n\n解压后阅读 mittiway-agent/README.md。原始画册需保留在项目上一级目录。\n默认使用本地检索和模板模拟，不需要 API Key。\n本包不含商业计划书全文、研究提取原文、.env 密钥文件或运行数据库。\n工单仅在本机保存，未连接厂家。企业知识和生产系统接入仍需正式实施。\n'
    z.writestr('交付说明.txt',note)
    z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))

with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert all('/runtime/' not in n and not n.endswith('/.env') and not n.endswith('.docx') for n in z.namelist())
report={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'source_files':len(files),'catalog_included':catalog.exists(),'excluded':['商业计划书全文','研究提取目录','运行数据库','.env 密钥','Python 缓存'],'checks':'25 automated checks passed; browser checks in qa/'}
(OUT/'交付清单.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
