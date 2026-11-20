"""A bounded customer-service workflow with server-owned conversation state."""
import re
import time
from .knowledge import normalize
from . import llm

INTENTS = {"company":"企业介绍", "products":"产品咨询", "parameters":"型号参数", "compare":"设备比较", "selection":"产品选型", "solution":"整线方案", "quote":"询价收集", "fault":"故障报修", "maintenance":"维护资料", "warranty":"售后政策", "human":"人工协助", "safety":"安全升级", "restricted":"访问边界", "unknown":"范围外问题"}
STATUS = {"answered":"已依据资料答复", "clarify":"待补充信息", "handoff":"建议人工处理", "conflict":"资料存在差异", "out_of_scope":"暂无可用证据"}

class ServiceAgent:
    def __init__(self, kb):
        self.kb = kb

    def classify(self, text, state):
        if re.search(r"短接|屏蔽.{0,5}(?:门|联锁|保护)|绕过.{0,5}(?:联锁|安全|急停)|带电|触电|冒烟|起火|漏电|安全门|急停.{0,4}(?:失效|失灵|不起作用)|拆.{0,3}护罩|PLC.{0,6}(?:修改|强制)|强制.{0,4}(?:PLC|输出)|bypass|interlock", text, re.I):
            return "safety"
        if re.search(r"系统提示|system\s*prompt|API.?KEY|密钥|内部成本|商业计划书|忽略.{0,10}(?:规则|指令|限制)|ignore.{0,10}instructions", text, re.I):
            return "restricted"
        if re.search(r"人工|投诉|客服经理|联系工程师|转接|售后电话", text):
            return "human"
        if re.search(r"保修|质保|退款|退货|售后政策", text):
            return "warranty"
        if re.search(r"故障|报警|报错|不动作|卡住|卡袋|卡箱|封口不牢|坏了|不能启动|不启动|漏气|(?:^|[^a-zA-Z])[EA]\d{2,}", text, re.I):
            return "fault"
        if re.search(r"保养|维护|维修|润滑|换刀|拆机|温度.{0,4}(?:调|设)|(?:设置|调整).{0,6}(?:温度|参数)", text):
            return "maintenance"
        if re.search(r"价格|多少钱|报价|询价|交期|发货|购买|预算|订单|物流|库存", text):
            return "quote"
        if re.search(r"区别|对比|比较|差别", text) or len(self.kb.extract_models(text)) >= 2:
            return "compare"
        if re.search(r"(?:纸箱|圆桶|桶|周转筐|飞机盒|水果盒|家电|外套袋|瓶盖|油脂|黄油|食品).{0,12}(?:用什么|选什么|推荐|选型)|推荐|选型|适合|怎么选|哪款|包装需求|需要.{0,8}(?:套袋|折盒)", text):
            return "selection"
        if re.search(r"整线|流水线|生产线|包装线|方案|工艺", text):
            return "solution"
        if self.kb.extract_models(text) and state.get("pending") in {"compare", "fault", "maintenance"} and not re.search(r"参数|速度|产能|供电|尺寸|规格|换型",text):
            return state["pending"]
        if self.kb.extract_models(text) or self.kb.unknown_models(text) or re.search(r"参数|速度|产能|电源|供电|气源|功率|规格|尺寸|节拍|换型", text):
            # A short slot answer continues the pending question instead of becoming a new parameter query.
            if state.get("pending") in {"selection", "solution", "quote", "fault", "maintenance"} and not self.kb.extract_models(text) and len(text) < 100:
                return state["pending"]
            return "parameters"
        if re.search(r"公司|成立|总部|企业|介绍|背景|哪里|主营|你们是谁", text):
            return "company"
        if re.search(r"产品|设备|套袋机|折盒机|封口机|扎带机|开箱机", text):
            return "products"
        if re.search(r"你好|您好|hello|hi|能做什么", text, re.I):
            return "greeting"
        if state.get("pending") and len(text) < 120 and re.search(r"纸箱|桶|筐|食品|油脂|粉末|瓶盖|尺寸|\d|没有|不清楚", text):
            return state["pending"]
        return "unknown"

    def extract_slots(self, text, previous):
        slots = dict(previous or {})
        models = self.kb.extract_models(text)
        if models:
            slots["models"] = models
        normalized = normalize(text)
        for key, pattern in [("industry", r"油脂|食品|颗粒粉末|粉末|瓶盖|生鲜|家电|化工|新能源|电商|脱水蔬菜|医药")]:
            match = re.search(pattern, normalized)
            if match:
                slots[key] = match.group()
        container = re.search(r"周转筐|圆桶|纸箱|飞机盒|水果盒|外套袋", normalized)
        if not container and "桶" in normalized:
            slots["container"] = "圆桶"
        elif container:
            slots["container"] = container.group()
        size = re.search(r"\d+(?:\.\d+)?\s*[×xX*＊]\s*\d+(?:\.\d+)?\s*[×xX*＊]\s*\d+(?:\.\d+)?\s*(?:mm|毫米|cm|厘米)?", text, re.I)
        if size:
            slots["size"] = size.group().strip()
        volume = re.search(r"\d+(?:\.\d+)?\s*(?:升|L)(?![a-zA-Z])", text, re.I)
        if volume and not size:
            slots["size"] = volume.group()
        throughput = re.search(r"(?:每分钟\s*\d+(?:\.\d+)?\s*(?:箱|个|桶|包)|\d+(?:\.\d+)?\s*(?:箱|个|桶|包)\s*(?:[/／每]\s*(?:分钟|小时)|每分|每时))", text)
        if throughput:
            slots["throughput"] = throughput.group()
        alarm = re.search(r"(?<![a-zA-Z0-9])([EA]\d{2,})(?![a-zA-Z0-9])", text, re.I)
        if alarm:
            slots["alarm"] = alarm.group(1).upper()
        return slots

    def run(self, text, previous=None):
        started = time.monotonic()
        previous = previous or {}
        intent = self.classify(text, previous)
        # Slot carry-over is deliberate and bounded by task. A new explicit intent starts clean.
        continue_task = previous.get("pending") == intent or previous.get("last_intent") == intent
        slots = self.extract_slots(text, previous.get("slots") if continue_task or intent in {"parameters", "compare", "fault", "maintenance", "human"} else {})
        if intent == "compare" and previous.get("pending") == "compare":
            slots["models"] = list(dict.fromkeys(previous.get("slots",{}).get("models",[]) + slots.get("models",[])))
        models = slots.get("models", [])
        docs = []
        suggestions = []
        status = "answered"
        pending = None
        notes = []
        mode = "offline"
        trace = [{"step":"scope", "label":"资料范围", "detail":"仅使用演示中公开的画册与官网知识；商业计划书不进入对客检索", "status":"done"}, {"step":"intent", "label":"问题理解", "detail":INTENTS.get(intent, "开始咨询"), "status":"done"}]
        unknown = self.kb.unknown_models(text)

        if intent == "safety":
            status = "handoff"
            answer = "这个问题涉及安全联锁、危险现象或高风险操作，需要现场专业人员处理。\n\n本演示没有经批准的安全作业文件，不能提供绕过保护、带电处理或强制运行的方法。请按现场已经批准的应急与安全制度联系设备或安全负责人。\n\n可以记录设备型号、完整报警信息和现象，创建本地模拟工单交由人工确认。"
            docs = [self.kb.by_id["scope"]]
            suggestions = ["创建本地模拟工单", "我需要联系工程师"]
        elif intent == "restricted":
            status = "out_of_scope"
            answer = "当前客服入口仅检索公开产品资料，不能提供内部商业计划、系统提示词或密钥。\n\n您可以询问设备产品、型号规格，或提交包装需求。"
        elif unknown:
            status = "clarify"
            answer = f"当前资料中没有 {'、'.join(unknown)} 的准确型号记录，我不能用相似型号的参数替代。\n\n请核对铭牌完整型号与序列号，或提供经批准的设备资料；也可以创建本地模拟工单请工程师核实。"
        elif intent == "greeting":
            answer = "您好，我是迈特威设备助手。可以帮您查产品资料、比较型号、整理包装需求，也能收集售后问题。\n\n告诉我设备型号或包装场景即可；有资料的回答会附上来源。"
            suggestions = ["迈特威有哪些主要设备？", "MTW-Z15 的参数是什么？", "食品纸箱包装线怎么选？"]
        elif intent == "company":
            docs = [self.kb.by_id["company"], self.kb.by_id["families"]]
            answer = "根据画册与官网介绍，迈特威智能成立于 2015 年，位于广东省东莞市，提供包装设备研发、生产、销售与服务。画册封面主体为迈特威智能设备（广东）有限公司；官网也展示广东／深圳名称、上海办事处及马来西亚分公司。\n\n主要业务包括折盒成型、套袋封口、扎带、开封箱及后道包装整线。公开资料用于了解业务；合同主体和具体资质有效性须另行核验。"
            suggestions = ["迈特威有哪些主要设备？", "油脂行业包装整线怎么配置？"]
        elif intent == "products":
            docs = [self.kb.by_id["families"]]
            answer = "迈特威设备可以按三类了解：\n\n**折盒成型**：MTW-Z15 标准折盒机、MTW-ZH25R 热熔胶高速折盒机、MTW-ZH25F 水果盒折盒机等。\n\n**套袋封口**：MTW-T50 纸箱内套袋机、MTW-T50Y 圆桶内套袋机、MTW-CMT50 成品袋套袋机、MTW-TF50 提袋封口机等。\n\n**装箱开封箱与整线**：机器人开箱、自动开箱、装箱、封箱，并组合后道包装线。\n\n告诉我物料、容器和目标节拍，可以进一步缩小候选范围。"
            suggestions = ["我需要纸箱内套袋设备", "MTW-Z15 的参数是什么？", "MTW-T50 和 MTW-T50H 有什么区别？"]
        elif intent in {"parameters", "compare"}:
            if not models:
                status, pending = "clarify", "parameters"
                answer = "请提供完整设备型号，例如 MTW-Z15、MTW-T50H 或 MTW-T50Y。\n\n不同型号、配置和资料版本的速度与规格不同，确认型号后我会列出参数及出处。"
                suggestions = ["MTW-Z15 的参数是什么？", "MTW-T50 的速度是多少？"]
            else:
                docs = [self.kb.by_model[normalize(m)] for m in models]
                if "MTW-T50" in models:
                    status = "conflict"
                    docs.append(self.kb.by_id["t50-conflict"])
                    answer = "**MTW-T50 的两个来源存在参数差异，需要先核实配置。**\n\n| 来源 | 参考速度 | 供电字段 |\n|---|---|---|\n| 2026 画册 · 印刷页 19 | 360–480 个/小时 | 380V / 50Hz / 8kW |\n| 官网 MTW-T50 产品页 | 300–1200 个/小时（可定制） | 380V / 60Hz / 3kW |\n\n不能将这两套参数合并，也不能仅凭检索时间判断哪套适用于您的设备。请核对铭牌、序列号和合同技术协议后交工程师确认。"
                    if len(models)>1:
                        answer += "\n\n其他候选型号的画册参数：\n" + "\n".join(f"• {d['model']} {d['title']}：{d['specs']['参考速度']}；{d['specs']['适用规格']}。" for d in docs if d["kind"]=="product" and d["model"]!="MTW-T50")
                elif intent == "compare" and len(models) < 2:
                    status, pending = "clarify", "compare"
                    answer = "已识别型号 " + models[0] + "。请再提供一个完整型号，我会按用途、速度单位、适用规格和出处比较。"
                elif len(models) >= 2:
                    answer = "以下是公开资料中的初步对比：\n\n| 型号 | 用途 | 参考速度 | 适用规格 |\n|---|---|---|---|\n" + "\n".join(f"| {d['model']} | {d['title']} | {d['specs']['参考速度']} | {d['specs']['适用规格']} |" for d in docs)
                    answer += "\n\n参数仅适用于所引资料的配置。速度单位、袋型、物料和工位不同，不能单凭数值大小判断整线适用性。"
                else:
                    d = docs[0]
                    answer = f"**{d['model']} · {d['title']}**\n\n{d['summary']}\n\n" + "\n".join(f"• {k}：{v}" for k,v in d["specs"].items())
                    if d.get("note"):
                        answer += "\n\n资料提示：" + d["note"]
                    answer += "\n\n以上是对应来源的参考配置，实际选型与性能须结合样品和技术协议确认。"
                suggestions = ["我想提交包装需求", "我需要联系工程师"]
        elif intent in {"selection", "solution", "quote"}:
            # Query rewrite uses only this task's slots, never a client-provided role or arbitrary history.
            query = text + " " + " ".join(str(v) for k,v in slots.items() if k != "models")
            hits = self.kb.search(query, kinds={"product", "solution"}, limit=8)
            container = slots.get("container", "")
            preferred = {"纸箱":["MTW-T50", "MTW-T50H", "MTW-TF50"], "圆桶":["MTW-T50Y", "MTW-TF50Y"], "周转筐":["MTW-T50Z"], "飞机盒":["MTW-Z15"], "水果盒":["MTW-ZH25F"], "外套袋":["MTW-JD100"]}.get(container, [])
            if preferred:
                docs = [self.kb.by_model[normalize(m)] for m in preferred[:2]]
            elif models:
                docs = [self.kb.by_model[normalize(m)] for m in models[:2]]
            else:
                docs = [r["document"] for r in hits[:2]]
            if intent == "solution":
                solution_id = "line-oil" if slots.get("industry") == "油脂" else "line-food"
                docs = [self.kb.by_id[solution_id]] + docs[:2]
            missing = [(key,label) for key,label in [("industry","物料或行业"),("container","容器类型（纸箱／桶／周转筐／纸盒）"),("size","容器长×宽×高及单位，或桶容积"),("throughput","目标节拍与单位（箱／分钟或桶／小时）")] if not slots.get(key)]
            status = "clarify" if missing else "handoff"
            pending = intent
            if intent == "quote":
                answer = "我可以整理询价需求。目前知识库没有正式价格、库存、订单或交期数据，不能给出确定报价或承诺。\n\n"
            elif intent == "solution":
                answer = "可先按公开案例梳理后道包装链路：开箱 → 套袋 → 装料／灌装 → 内袋封口或折袋 → 封箱 → 检测／码垛。工位组合和顺序须按现场方案确认。\n\n"
            else:
                answer = "可以先根据包装场景筛选候选设备。\n\n"
            product_docs = [d for d in docs if d["kind"] == "product"]
            if product_docs:
                answer += "**初步候选（待工程确认）**\n" + "\n".join(f"• {d['model']} {d['title']}：{d['summary']}" for d in product_docs) + "\n\n"
            if slots:
                labels = {"industry":"物料／行业", "container":"容器", "size":"规格", "throughput":"目标节拍"}
                collected = [f"{labels[k]}：{v}" for k,v in slots.items() if k in labels]
                if collected:
                    answer += "已记录：" + "；".join(collected) + "。\n\n"
            if missing:
                answer += "为了缩小范围，请补充：\n" + "\n".join(f"• {label}" for _,label in missing[:3])
            else:
                answer += "需求字段已基本齐全，可以创建本地模拟工单，交工程师复核袋材、实际尺寸、卫生或防爆要求、上下游接口及整线节拍。这里记录的是您的目标产能，不代表设备已经满足该要求。"
            if any(d.get("model")=="MTW-T50" for d in docs):
                answer += "\n\nMTW-T50 跨来源参数存在差异，当前只将其作为用途候选。"
            suggestions = ["物料是食品，使用纸箱", "尺寸400×300×300 mm，12箱/分钟"] if missing else ["创建本地模拟工单", "MTW-T50 的参数是什么？"]
        elif intent in {"fault", "maintenance"}:
            docs = [self.kb.by_id["scope"]]
            if models:
                docs = [self.kb.by_model[normalize(models[0])]] + docs
            pending = intent
            status = "clarify" if not models else "handoff"
            if intent == "fault":
                answer = "我可以先整理故障信息。目前只有产品画册与公开产品资料，没有经批准的报警码表或维修手册，不能据此确定故障原因或编造处理步骤。\n\n"
            else:
                answer = "目前没有经企业批准的维护手册、点检计划或 SOP，不能确认保养周期、润滑点、参数设定或拆装步骤。产品宣传画册不能代替操作规程。\n\n"
            if models:
                answer += "已识别设备：" + "、".join(models) + "。"
                if slots.get("alarm"):
                    answer += f"已记录报警 {slots['alarm']}，该代码的厂家定义尚未取得。"
                answer += "\n\n请准备设备序列号、控制器版本、完整报警文字、发生时间及现象，在安全条件下提供现有照片或记录。可创建本地模拟工单交人工处理。"
            else:
                answer += "请先提供铭牌完整型号、完整报警代码或画面文字、现象与发生时间；型号不同，报警含义可能不同。"
            suggestions = ["设备型号 MTW-T50，报警 E001", "创建本地模拟工单"]
        elif intent == "warranty":
            status = "handoff"
            docs = [self.kb.by_id["scope"]]
            answer = "现有画册和公开资料不足以确认您的保修期限、免费维修范围或退换政策。具体约定应以采购合同、保修文件和设备序列号为依据。\n\n可以先创建本地模拟工单，记录型号和问题，由人工核对。"
            suggestions = ["创建本地模拟工单"]
        elif intent == "human":
            status = "handoff"
            answer = "可以为当前问题创建本地模拟工单，保留已收集的设备与需求信息。\n\n本演示没有接入厂家客服或 CRM，工单保存在当前电脑，不会自动发送，也没有人工在线响应承诺。正式上线后可对接企业工单系统并展示真实受理状态。"
            suggestions = ["创建本地模拟工单"]
        else:
            status = "out_of_scope"
            answer = "当前资料中没有足以回答这个问题的依据。这个助手主要支持迈特威设备产品、包装需求和售后信息收集。\n\n可以提供设备型号，或说明物料、容器和目标节拍；超出公开资料的问题可交人工确认。"
            suggestions = ["迈特威有哪些主要设备？", "我需要联系工程师"]

        if docs:
            trace.append({"step":"retrieve", "label":"检索资料", "detail":f"命中 {len(docs)} 条公开知识，按型号与资料来源组织", "status":"done"})
        else:
            trace.append({"step":"retrieve", "label":"检索资料", "detail":"本轮未采用可回答问题的知识证据", "status":"skipped"})
        trace.append({"step":"validate", "label":"证据与边界检查", "detail":"发现跨来源差异，未自动选定参数" if status=="conflict" else "检查资料适用范围；缺少维修资料时升级人工", "status":"warning" if status in {"conflict","handoff"} else "done"})

        # No external model sees faults, actions, missing evidence or conflicts.
        if llm.configured() and status == "answered" and intent in {"company", "products", "parameters", "compare"} and docs:
            try:
                answer, ref_ids = llm.generate(text, docs)
                docs = [d for d in docs if d["id"] in ref_ids]
                mode = "llm"
                notes.append("已通过引用ID、结构与数字检查；语义是否被完整支持仍需企业复核。")
            except Exception:
                mode = "offline_fallback"
                notes.append("模型服务未完成或输出校验失败，已使用本地资料答复。")
        trace.append({"step":"response", "label":"答复与后续", "detail":STATUS.get(status), "status":"done"})
        state = {"slots": slots, "pending": pending, "last_intent": intent}
        return {"answer":answer, "intent":intent, "intent_label":INTENTS.get(intent,"开始咨询"), "status":status, "status_label":STATUS[status], "citations":self.kb.citations(docs), "trace":trace, "suggestions":suggestions, "state":state, "slots":slots, "mode":mode, "notes":notes, "latency_ms":round((time.monotonic()-started)*1000), "can_create_ticket":status in {"handoff","conflict","clarify","out_of_scope"}, "disclaimer":"本地开发模拟，资料尚待企业审核；工单未连接厂家。"}
