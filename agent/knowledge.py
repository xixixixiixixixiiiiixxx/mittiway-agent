"""Chinese character bigram BM25 and exact-model retrieval; no hidden embedding call."""
from collections import Counter
from pathlib import Path
import json
import math
import re

SYNONYMS = {"胶筐": "周转筐", "塑料筐": "周转筐", "周转框": "周转筐", "胶框": "周转筐", "快递盒": "飞机盒", "奶油": "油脂", "黄油": "油脂", "包膜": "套袋", "每分钟": "/分钟"}

def normalize(value):
    value = value.upper().replace("－", "-").replace("–", "-")
    for a, b in SYNONYMS.items():
        value = value.replace(a, b)
    return value

def tokens(value):
    value = normalize(value)
    result = re.findall(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", value)
    for segment in re.findall(r"[\u4e00-\u9fff]+", value):
        result += [segment[i:i+2] for i in range(len(segment)-1)]
        if len(segment) == 1:
            result.append(segment)
    return result

class KnowledgeBase:
    def __init__(self, path):
        self.data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.documents = self.data["documents"]
        self.by_id = {d["id"]: d for d in self.documents}
        self.products = [d for d in self.documents if d["kind"] == "product"]
        self.by_model = {normalize(d["model"]): d for d in self.products}
        self.term_counts = {d["id"]: Counter(tokens(d["title"] + " " + d["text"])) for d in self.documents}
        self.df = Counter()
        for count in self.term_counts.values():
            self.df.update(count.keys())
        self.avg_len = sum(sum(c.values()) for c in self.term_counts.values()) / max(len(self.documents), 1)

    def extract_models(self, text):
        normalized = normalize(text)
        found = []
        # Full boundaries prevent T50 from matching T50H or TF50.
        for model in sorted(self.by_model, key=len, reverse=True):
            if re.search(r"(?<![A-Z0-9])" + re.escape(model) + r"(?![A-Z0-9])", normalized):
                found.append(self.by_model[model]["model"])
        if found:
            return found
        for model in sorted(self.by_model, key=len, reverse=True):
            short = model.removeprefix("MTW-")
            if re.search(r"(?<![A-Z0-9-])" + re.escape(short) + r"(?![A-Z0-9])", normalized):
                found.append(self.by_model[model]["model"])
        return found

    def unknown_models(self, text):
        all_codes = re.findall(r"MTW-[A-Z0-9]+", normalize(text))
        return [m for m in all_codes if m not in self.by_model]

    def visible(self, d, audience="public"):
        return d.get("visibility") == audience and d.get("review_status") in {"approved", "demo_reviewed"}

    def search(self, query, limit=5, kinds=None, models=None, audience="public"):
        q = set(tokens(query))
        result = []
        for d in self.documents:
            if not self.visible(d, audience) or (kinds and d["kind"] not in kinds):
                continue
            if models and d["kind"] == "product" and d["model"] not in models:
                continue
            counts = self.term_counts[d["id"]]
            length = sum(counts.values())
            score = 0.0
            for term in q:
                freq = counts.get(term, 0)
                if freq:
                    idf = math.log(1 + (len(self.documents)-self.df[term]+0.5)/(self.df[term]+0.5))
                    score += idf * (freq*2.5)/(freq + 1.5*(0.25+0.75*length/self.avg_len))
            if models and any(m in d.get("models", []) for m in models):
                score += 50
            if score > 0:
                result.append({"document": d, "score": round(score,3)})
        return sorted(result, key=lambda r:r["score"], reverse=True)[:limit]

    def citations(self, docs):
        result = []
        seen = set()
        for d in docs:
            if not self.visible(d):
                continue
            for source in d["sources"]:
                key = (source["id"], d["id"])
                if key in seen:
                    continue
                seen.add(key)
                result.append({**source, "document_id":d["id"], "document_title":d["title"], "excerpt":d["text"][:550], "review_status":d["review_status"]})
        return result[:8]
