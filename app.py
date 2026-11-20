"""Local-only demonstration server. Run with the documented WorkBuddy Python."""
from argparse import ArgumentParser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import json
import mimetypes
import os
import re
import secrets
import sys
import threading

from agent.engine import ServiceAgent
from agent.knowledge import KnowledgeBase
from agent.store import Store, redact

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
CATALOG = ROOT.parent / "2026 迈特威画册.pdf"

def load_env():
    path = ROOT / ".env"
    allowed = {"AGENT_MODE","LLM_API_BASE","LLM_MODEL","LLM_API_KEY"}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=",1)
            if key.strip() in allowed:
                os.environ.setdefault(key.strip(),value.strip().strip("\"'"))

class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self,address,data_path=None):
        super().__init__(address, Handler)
        self.kb = KnowledgeBase(ROOT / "data" / "knowledge.json")
        self.agent = ServiceAgent(self.kb)
        self.store = Store(data_path or ROOT / "runtime" / "service.sqlite3")
        self.locks = {}
        self.locks_guard = threading.Lock()
        self.allowed_hosts = {f"localhost:{self.server_port}", f"127.0.0.1:{self.server_port}"}

    def lock_for(self,cid):
        with self.locks_guard:
            return self.locks.setdefault(cid,threading.Lock())

class Handler(BaseHTTPRequestHandler):
    server_version = "MittiwayDemo/1.0"

    def log_message(self, fmt, *args):
        # Never echo query contents, request bodies, model errors or credentials.
        return

    def common_check(self):
        if self.headers.get("Host") not in self.server.allowed_hosts:
            self.error(403,"此演示只允许本机访问")
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://"+h for h in self.server.allowed_hosts}:
            self.error(403,"不接受跨站请求")
            return False
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            cookie = SimpleCookie()
        value = cookie.get("mittiway_browser")
        value = value.value if value else ""
        self.new_cookie = not bool(re.fullmatch(r"[a-f0-9]{48}", value))
        self.owner = secrets.token_hex(24) if self.new_cookie else value
        return True

    def send_bytes(self,data,status=200,content_type="application/json; charset=utf-8",extra=None):
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")
        if getattr(self,"new_cookie",False):
            self.send_header("Set-Cookie",f"mittiway_browser={self.owner}; HttpOnly; SameSite=Strict; Path=/")
        for k,v in (extra or {}).items():
            self.send_header(k,v)
        self.end_headers()
        self.wfile.write(data)

    def json(self,value,status=200,extra=None):
        self.send_bytes(json.dumps(value,ensure_ascii=False).encode("utf-8"),status,extra=extra)

    def error(self,status,message):
        self.json({"error":message},status)

    def do_GET(self):
        if not self.common_check():
            return
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.json({"ok":True,"mode":"llm_configured" if os.getenv("AGENT_MODE")=="llm" else "offline", "products":len(self.server.kb.products),"knowledge_records":len(self.server.kb.documents)})
        if path == "/api/bootstrap":
            return self.json({"company":self.server.kb.data["company"], "brand":"MITTIWAY", "as_of":self.server.kb.data["as_of"], "mode":"llm_configured" if os.getenv("AGENT_MODE")=="llm" else "offline", "products":len(self.server.kb.products), "knowledge_records":len(self.server.kb.documents), "catalog_pages":23, "conversations":self.server.store.list_conversations(self.owner),"gaps":self.server.kb.data["gaps"]})
        if path == "/api/knowledge":
            documents = [d for d in self.server.kb.documents if self.server.kb.visible(d)]
            return self.json({"documents":documents,"gaps":self.server.kb.data["gaps"],"design_input": {"title":"企业专属AI助手商业计划书", "indexed_for_customer":False}})
        if path == "/api/conversations":
            return self.json({"conversations":self.server.store.list_conversations(self.owner)})
        if path == "/api/tickets":
            return self.json({"tickets":self.server.store.tickets(self.owner)})
        if path.startswith("/api/conversations/"):
            cid = path.removeprefix("/api/conversations/")
            conv = self.server.store.conversation(self.owner,cid)
            return self.json(conv) if conv else self.error(404,"会话不存在或无权访问")
        if path.startswith("/api/export/"):
            cid = path.removeprefix("/api/export/")
            conv = self.server.store.conversation(self.owner,cid)
            if not conv:
                return self.error(404,"会话不存在或无权访问")
            return self.json(conv,extra={"Content-Disposition":f'attachment; filename="mittiway-{cid[:8]}.json"'})
        if path == "/files/catalog":
            if not CATALOG.is_file():
                return self.error(404,"请将原始画册放在项目的上一级目录")
            return self.send_bytes(CATALOG.read_bytes(),content_type="application/pdf",extra={"Content-Disposition":"inline; filename=mittiway-catalog-2026.pdf"})
        if path == "/guide":
            return self.send_bytes((STATIC/"index.html").read_bytes(),content_type="text/html; charset=utf-8")
        routes = {"/":"index.html","/index.html":"index.html","/app.js":"app.js","/styles.css":"styles.css","/favicon.svg":"favicon.svg"}
        if path in routes:
            file = STATIC/routes[path]
            mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            if mime.startswith("text/") or file.suffix==".js":
                mime += "; charset=utf-8"
            return self.send_bytes(file.read_bytes(),content_type=mime)
        return self.error(404,"页面不存在")

    def read_body(self):
        if self.headers.get("Content-Type","").split(";")[0].strip() != "application/json":
            raise ValueError("请使用 JSON 请求")
        try:
            length = int(self.headers.get("Content-Length","0"))
        except ValueError:
            raise ValueError("请求长度无效")
        if length <= 0 or length > 16384:
            raise ValueError("请求内容为空或过长")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value,dict):
            raise ValueError("请求内容应为对象")
        return value

    def do_POST(self):
        if not self.common_check():
            return
        try:
            body = self.read_body()
            path = urlparse(self.path).path
            if path == "/api/conversations":
                return self.json(self.server.store.create_conversation(self.owner),201)
            if path == "/api/chat":
                question = body.get("message")
                if not isinstance(question,str) or not question.strip() or len(question)>2000:
                    raise ValueError("请输入 1–2000 个字符的问题")
                cid = body.get("conversation_id")
                if cid is None:
                    cid = self.server.store.create_conversation(self.owner)["id"]
                if not isinstance(cid,str):
                    raise ValueError("会话编号无效")
                with self.server.lock_for(cid):
                    conv = self.server.store.conversation(self.owner,cid)
                    if not conv:
                        return self.error(404,"会话不存在或无权访问")
                    result = self.server.agent.run(redact(question.strip()),conv["state"])
                    answer_id = self.server.store.save_turn(self.owner,cid,question,result)
                return self.json({**result,"conversation_id":cid,"message_id":answer_id})
            if path == "/api/tickets":
                cid = body.get("conversation_id")
                details = body.get("details","")
                category = body.get("category","consultation")
                key = body.get("idempotency_key")
                if not isinstance(cid,str) or not isinstance(details,str) or len(details)>2000:
                    raise ValueError("工单信息无效或过长")
                if category not in {"consultation","fault","selection"}:
                    raise ValueError("请选择有效工单类别")
                if not isinstance(key,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}",key):
                    raise ValueError("缺少有效的幂等编号")
                result = self.server.store.create_ticket(self.owner,cid,category,details,key)
                return self.json(result,201)
            if path == "/api/feedback":
                if body.get("rating") not in {"helpful","unhelpful"} or not isinstance(body.get("message_id"),str):
                    raise ValueError("反馈内容无效")
                self.server.store.feedback(self.owner,body["message_id"],body["rating"])
                return self.json({"ok":True})
            return self.error(404,"接口不存在")
        except PermissionError:
            return self.error(404,"记录不存在或无权访问")
        except (ValueError,TypeError,json.JSONDecodeError):
            return self.error(400,"请求格式或字段无效，请检查输入")
        except Exception:
            return self.error(500,"本地服务暂未完成请求，请重试")

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    load_env()
    parser = ArgumentParser()
    parser.add_argument("--port",type=int,default=8765)
    args = parser.parse_args()
    server = LocalServer(("127.0.0.1",args.port))
    print(f"Mittiway service demo: http://127.0.0.1:{server.server_port}",flush=True)
    print("Mode: local simulation. Tickets are saved locally only.",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
