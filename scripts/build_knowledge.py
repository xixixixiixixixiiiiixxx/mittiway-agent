"""Build a reviewed demonstration corpus, without treating sales literature as a manual."""
from pathlib import Path
import json
import hashlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-11-20"
CATALOG = "2026 迈特威画册.pdf"

def catalog_source(page, printed):
    return {"id": f"catalog-{page}", "title": CATALOG, "type": "catalog", "url": f"/files/catalog#page={page}", "page": page, "locator": f"PDF 第 {page} 页 · 印刷页 {printed}", "version": "2026 画册（按文件名标识，发行日未载明）", "accessed_at": DATE}

def web_source(slug, title, url, locator):
    return {"id": slug, "title": title, "type": "web", "url": url, "locator": locator, "version": f"网页检索快照 {DATE}", "accessed_at": DATE}

ABOUT = web_source("web-about", "迈特威官网 · 公司简介", "https://www.miteway.com/32/", "公司简介")
WEB_T50 = web_source("web-t50", "迈特威官网 · MTW-T50", "https://www.miteway.com/zxtdj/1003", "产品参数表")
WEB_T50G = web_source("web-t50g", "迈特威官网 · MTW-T50G", "https://www.miteway.com/zxtdj/1002", "产品参数表")
WEB_Z15 = web_source("web-z15", "迈特威官网 · MTW-Z15", "https://www.miteway.com/58/1015", "产品参数表")
WEB_FT50 = web_source("web-ft50", "迈特威官网 · MTW-FT50", "https://www.miteway.com/56/2008", "产品名称与参数表")
WEB_HOME = web_source("web-home", "迈特威官网 · 产品与整线案例", "https://www.miteway.com/", "产品系列与客户案例")

products = []

def product(model, name, category, industries, page, printed, speed, size, summary, extra=None, sources=None, note=""):
    specs = {"参考速度": speed, "适用规格": size}
    specs.update(extra or {})
    source_list = sources or [catalog_source(page, printed)]
    text = f"{model} {name}。{summary} 适用行业：{'、'.join(industries)}。" + " ".join(f"{k}：{v}。" for k, v in specs.items())
    products.append({"id": model.lower().replace(" ", "-"), "kind": "product", "model": model, "models": [model], "title": name, "category": category, "industries": industries, "summary": summary, "specs": specs, "text": text, "note": note, "sources": source_list, "version": "demo-2026.11.20", "visibility": "public", "review_status": "demo_reviewed", "effective_date": None, "owner": "演示资料整理（待企业指定审核人）"})

product("MTW-Z15", "标准折盒机", "折盒成型", ["电子产品", "食品", "电商", "化妆品", "玩具", "医药"], 5, "06", "720–1200 个/小时", "L170–270 × W120–170 × H30–60 mm", "用于飞机盒、天地盖等纸盒成型，可单机运行或配套包装线。", {"供电": "220V / 50Hz / 2kW", "参考换型时间": "10–15 分钟（手动调节）"}, [catalog_source(5,"06"), WEB_Z15])
product("MTW-ZH25D", "自动钉盒机", "折盒成型", ["电子产品", "汽车用品", "电商", "五金"], 6, "07", "900–1500 个/小时", "L300–500 × W300–400 × H60–100 mm", "同步取盒、冲压成型与钉盒，画册注明配套打钉机使用。")
product("MTW-CT300", "裹包机", "折盒成型", ["电子产品", "食品", "电商", "饮料", "玩具", "医药", "五金"], 6, "08", "300–600 个/小时", "L200–400 × W200–300 × H200–300 mm", "可结合自动取料成型、理料、装料和喷胶上盖，支持整线衔接。")
product("MTW-ZH25R", "热熔胶高速折盒机", "折盒成型", ["电子产品", "食品", "电商", "饮料", "玩具", "医药", "五金", "服装"], 7, "09", "1500–2400 个/小时", "L250–350 × W200–300 × H60–100 mm", "取盒、自动喷胶、冲压成型同步完成，画册注明需配套热熔胶机。")
product("MTW-ZH25F", "水果盒折盒机", "折盒成型", ["生鲜果蔬", "玩具", "五金"], 7, "10", "1500–1800 个/小时", "L250–350 × W200–300 × H50–100 mm", "面向水果盒等纸盒成型，支持折盒或配热熔胶封盒。")
product("MTW-G15R", "合盖机", "折盒成型", ["电子产品", "礼品", "电商", "日用品", "玩具", "五金"], 8, "11", "720–900 个/小时", "L250–350 × W200–300 × H40–70 mm", "用于盒盖折叠与合盖，可按方案配置热熔胶机。")
product("MTW-ZH15R", "三角立柱折盒机", "折盒成型", ["生鲜果蔬", "食品", "礼品", "日用品", "膨化食品"], 8, "12", "18–20 个/分钟", "L400–600 × W300–400 × H100–200 mm", "面向带三角立柱的盒型，提供自动取盒、喷胶与冲压成型。")
product("MTW-Cartoner A3", "成型装盒一体机", "折盒成型", ["食品", "礼品", "日用品", "化妆品", "医药", "咖啡", "巧克力", "电子产品"], 9, "13–14", "600–900 个/小时", "L200–300 × W200–300 × H60–90 mm", "集取盒、成型、放产品与喷胶粘合于一体。")
product("MTW-ZX10", "全自动高速装箱机", "装箱开封箱", ["食品", "礼品", "日用品", "化妆品", "医药", "咖啡", "电子产品"], 10, "15–16", "120 包/分钟（产品装箱速度）", "L550–650 × W350–450 × H150–400 mm", "取箱、自动堆叠物料、装箱、送箱；速度单位为包/分钟，不能当作箱/分钟。", note="画册的 120 bags/min 为产品包数，整线箱速需另行核算。")
product("MTW-TK50", "开箱套袋一体机", "套袋封口", ["瓶盖压泵", "汽车用品", "医药", "食品"], 11, "18", "300–600 个/小时", "L300–500 × W300–400 × H300–400 mm", "集开箱、封底、套袋、翻边与鼓风出箱于一体。", {"供电": "380V / 50Hz / 8kW"}, note="画册型号 TK50，不能直接等同于官网 MT540。")
product("MTW-T50", "纸箱内套袋机", "套袋封口", ["油脂化工", "颗粒粉末", "散装水果", "瓶盖压泵", "汽车用品", "医药"], 12, "19", "360–480 个/小时", "L300–500 × W300–400 × H300–400 mm", "完成纸箱进箱、套袋、翻边与鼓风出箱，可配提袋封口或折袋设备。", {"供电": "380V / 50Hz / 8kW", "气源": "600 NL/min / 0.6–0.8 MPa", "参考换型时间": "10–20 分钟（手动调节）"}, note="与官网同名型号的速度、供电及机重等字段存在差异；报价和工艺决策须确认设备序列号与配置。")
product("MTW-TF50", "纸箱内提袋封口机", "套袋封口", ["油脂化工", "颗粒粉末", "散装水果", "瓶盖压泵", "汽车用品", "医药"], 12, "20", "360–480 个/小时", "L300–500 × W300–400 × H300–400 mm", "完成提袋、封口及折袋压袋，与套袋设备配套。", {"供电": "380V / 50Hz / 6kW"}, note="本画册为 TF50；官网另有 FT50，未确认是同一配置。")
product("MTW-CMT50", "成品袋套袋机", "套袋封口", ["化学品", "颗粒粉末", "防水材料", "食品", "医药", "新能源"], 13, "21", "360–480 个/小时；高速版 1000–1200 个/小时", "L300–500 × W300–400 × H60–100 mm（按画册）", "适用于成品袋内套，选择前应核对袋型、袋尺寸、容器及材质。", note="画册中高度范围与部分同类机型差别较大，企业审核前不可自行改写。")
product("MTW-TZ50", "自动扎带机", "套袋封口", ["化学品", "颗粒粉末", "防水材料", "酱料", "日用品", "化妆品"], 13, "22", "200–300 个/小时", "L300–500 × W300–400 × H60–100 mm（按画册）", "可完成提袋、扎口与折袋压袋，画册展示铁丝、尼龙扎带方案。", note="画册扎带机型号为 TZ50；ZD50 在本画册指折袋机。")
product("MTW-T50Y", "圆桶内套袋机", "套袋封口", ["防水材料", "颗粒粉末", "化学品", "食品", "医药", "新能源"], 14, "23", "300–500 桶/小时", "圆桶 15–200 L", "对圆桶进桶、套袋、翻边与出桶，可配圆桶内提袋封口机。")
product("MTW-TF50Y", "圆桶内提袋封口机", "套袋封口", ["防水材料", "颗粒粉末", "化学品", "食品", "医药", "新能源"], 14, "24", "300–500 桶/小时", "圆桶 15–200 L", "面向圆桶内袋的提袋封口，与圆桶内套袋设备组合。")
product("MTW-T50H", "高速套袋机", "套袋封口", ["散装水果", "瓶盖压泵", "汽车用品", "坚果食品"], 15, "25", "1200–1500 个/小时", "L300–500 × W300–400 × H300–400 mm", "面向较高节拍的容器内套袋，与高速封口等设备配套。", {"供电": "380V / 50Hz / 8kW"}, note="画册型号 T50H 与官网 T50G 不自动合并。")
product("MTW-TF50H", "高速封口机", "套袋封口", ["散装水果", "瓶盖压泵", "汽车用品"], 15, "26", "900–1200 个/小时", "L300–500 × W300–400 × H300–400 mm", "完成提袋、抽气、封口与压袋出箱，可配高速套袋设备。")
product("MTW-JD100", "产品外套袋机", "套袋封口", ["家电", "汽车用品"], 16, "27", "240–300 个/小时", "L600–800 × W600–800 × H600–1000 mm", "完成进料、定位、外套袋和出料，适用于产品外包装。")
product("MTW-ZD50", "自动折袋机", "套袋封口", ["日用品", "化妆品", "散装水果", "瓶盖压泵", "汽车用品", "医药", "颗粒粉末"], 16, "28", "300–720 个/小时", "L300–500 × W300–400 × H300–400 mm", "完成提袋、折袋与压料，可配纸箱自动套袋机。", note="不得与官网部分旧页面的 ZD50 扎带机描述无条件合并。")
product("MTW-T50Z", "周转筐套袋机", "套袋封口", ["生鲜肉类", "脱水蔬菜", "烟草"], 17, "29", "300–500 个/小时", "L400–600 × W300–500 × H150–300 mm", "为周转筐或相应容器内套袋，可配提袋封口、折袋及装箱线。")
product("MTW-RB50", "机器人开箱", "装箱开封箱", ["食品", "日用品", "通用制造"], 17, "30", "360–600 个/小时", "L300–500 × W300–400 × H300–400 mm", "机器人开箱与折底封底，可与自动包装线衔接。", note="画册 RB50 不自动等同于官网 JK50 或正文 JK60。")
product("MTW-K40", "自动开箱机", "装箱开封箱", ["食品", "日用品", "通用制造"], 18, "31", "6–12 箱/分钟", "L250–450 × W100–400 × H100–400 mm", "纸箱开箱、折底与封底，可单机使用或配包装线。")
product("MTW-C50", "自动折盖封箱机", "装箱开封箱", ["食品", "日用品", "通用制造"], 18, "32", "输送速度 20 m/min", "L200–600 × W150–500 × H150–500 mm", "自动折盖并用胶带封箱。输送速度不可直接转换成箱/分钟。", note="画册为输送线速度，箱速与箱长、间距、工艺有关。")
product("MTW-T50G", "高速套袋机（官网）", "套袋封口", ["油脂化工", "颗粒粉末", "油漆", "水产"], None, None, "10–25 箱/分钟（按需定制）", "以实际容器尺寸为准", "官网展示的高速套袋型号；不能据此保证客户现场的整线节拍。", {"供电": "380V / 50Hz / 6kW"}, [WEB_T50G], note="与画册 T50H 的命名关系待确认。")
product("MTW-FT50", "纸箱内提袋封口机（官网）", "套袋封口", ["包装线配套"], None, None, "240–320 个/小时", "L300–500 × W300–400 × H300–400 mm", "官网独立列示的提袋封口型号，与画册 TF50 的配置关系待核实。", {"供电": "380V / 50Hz / 6kW"}, [WEB_FT50], note="不可自动按字母相近映射到 TF50。")

def doc(id, title, kind, text, sources, **kw):
    return {"id": id, "title": title, "kind": kind, "models": [], "category": "企业与服务", "text": text, "sources": sources, "version": "demo-2026.11.20", "visibility": "public", "review_status": "demo_reviewed", "effective_date": None, "owner": "演示资料整理（待企业审核）", **kw}

documents = products + [
    doc("company", "公司背景与主营业务", "company", "迈特威智能设备（广东）有限公司是画册封面的公司主体。2026画册与官网介绍均载明企业成立于2015年，位于广东省东莞市，业务包括自主研发、生产、销售与服务。官网同时展示广东、深圳名称及上海办事处、马来西亚分公司。主要产品为套袋、折盒、封口、扎带、开封箱及后道包装整线。工商主体、资质有效期和具体合同主体应另行核验。", [catalog_source(1,"封底/封面"), catalog_source(3,"01–02"), ABOUT]),
    doc("families", "产品家族与应用范围", "company", "折盒成型：标准飞机盒和天地盖折盒机、热熔胶粘盒机、水果盒折盒机、钉盒机、裹包机、合盖机与成型装盒一体机。套袋封口：纸箱内套袋、圆桶内套袋、周转筐套袋、成品袋套袋、产品外套袋、提袋封口、折袋与扎带。整线配套：机器人开箱、开箱机、装箱机与折盖封箱机。应用覆盖食品、油脂化工、颗粒粉末、瓶盖、家电、电商、医药、新能源等。", [catalog_source(2,"目录"), WEB_HOME]),
    doc("line-oil", "油脂后道包装整线", "solution", "2026画册展示全自动油脂包装整线。可组合开箱、套袋、灌装、内袋封口、封箱、检测与码垛等工位，实际工艺与设备组合依产品和客户方案确定。选择方案前需收集物料、温度与粘度、箱桶及袋尺寸、目标产能、现场空间和现有设备接口。画册中的提效与节人成果为宣传案例数据，不能作为任意客户的保证。", [catalog_source(20,"35–36"), WEB_HOME], category="整线方案", industries=["油脂", "食品"]),
    doc("line-food", "脱水蔬菜与食品整线", "solution", "2026画册展示脱水蔬菜包装整线，涵盖容器与内袋包装、称重灌装、封口及码垛等组合。食品、瓶盖、肉类、坚果、果蔬等有不同包装需求。选型须明确物料形态、箱或筐或桶、袋型、卫生要求、目标节拍、检测工位与上下游接口。不能用单机的最高宣传速度直接承诺整线稳定产能。", [catalog_source(19,"33–34"), catalog_source(22,"39–40")], category="整线方案", industries=["食品", "脱水蔬菜", "生鲜", "瓶盖", "果蔬"]),
    doc("t50-conflict", "MTW-T50 跨来源参数差异", "conflict", "同名MTW-T50在2026画册与官网产品参数中存在差异。画册印刷页19（PDF第12页）：360–480个/小时，380V/50Hz/8kW；官网产品页：300–1200个/小时（可定制），380V/60Hz/3kW。两个范围和供电字段不可拼接成一套参数，也不可仅按网页抓取日期决定设备真实配置。须以设备铭牌、序列号、合同技术协议和企业确认的现行配置为准。", [catalog_source(12,"19"), WEB_T50], models=["MTW-T50"]),
    doc("model-conflict", "型号名称与版本须精确核对", "conflict", "画册与官网存在命名差异：画册高速套袋 T50H 与官网 T50G；画册提袋封口 TF50 与官网 FT50；画册机器人开箱 RB50 与官网列表 JK50（正文另写 JK60）；画册 TZ50 为扎带机、ZD50 为折袋机，而官网部分页面把 ZD50 用于扎带机。仅凭相似字母不能确认同机型、同配置或可替换。", [catalog_source(13,"21–22"),catalog_source(15,"25–26"),catalog_source(16,"27–28"),catalog_source(17,"29–30"),WEB_HOME]),
    doc("scope", "本演示客服范围与资料缺口", "policy", "本项目为开发模拟：可回答企业与产品资料、按公开规格做初步候选建议、收集需求、记录报修和创建本地模拟工单。缺少经企业批准的报警码表、维护手册、SOP、真实报价、库存、订单、合同和保修条款，不提供确定故障诊断、维修步骤、价格、交期、订单查询结果或保修结论。安全联锁、电气带电操作、拆护罩运行、PLC安全参数等需交由专业人员。", [{"id":"demo-scope","title":"演示范围说明（开发设定）","type":"demo_policy","url":"/guide#scope","locator":"开发设定；不代表厂家政策","version":"demo-2026.11.20","accessed_at":DATE}]),
]

for d in documents:
    d["content_hash"] = hashlib.sha256(d["text"].encode()).hexdigest()

data = {"company": "迈特威智能设备（广东）有限公司", "brand": "MITTIWAY", "as_of": DATE, "mode": "local_demo", "product_count": len(products), "documents": documents,
        "design_input": {"title":"企业专属AI助手商业计划书.docx","visibility":"design_only","indexed_for_customer":False,"notes":"用于限定试点范围、来源展示、资料缺失升级及知识治理设计，不提供给对客检索和外部模型。"},
        "gaps": ["经批准的操作与维修手册", "按型号和控制器版本划分的报警码表", "SOP与保养计划", "维修工单及闭环案例", "价格、保修、交期与备件政策", "企业账号权限与真实工单接口"]}
(ROOT/"data").mkdir(exist_ok=True)
(ROOT/"data"/"knowledge.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(products)} products and {len(documents)} knowledge records.")
