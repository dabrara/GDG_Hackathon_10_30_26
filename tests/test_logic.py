"""Offline tests for real backend logic. Does not test FastAPI routes or a live model."""
import ast
import asyncio
import html
import httpx
import json
import re
import unittest
from pathlib import Path
from jsonschema import validate

SOURCE = Path(__file__).resolve().parents[1] / "app" / "main.py"
NAMES = {"STR", "ANALYZE_SCHEMA", "TEXT_SCHEMA", "QUIZ_SCHEMA", "UI_KEYS", "UI_SCHEMA", "CHAT_ADDENDUM", "HELP_ADDENDUM",
         "TOOLS", "system_prompt", "parse_json", "structured", "run_tool", "get_session", "export", "norm", "ground",
         "ndjson", "ollama_chat", "apply_translation", "speed_estimate", "model_info", "LATEST_SIZE", "UNSUPPORTED"}
class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail
        super().__init__(detail)

def load_logic():
    tree = ast.parse(SOURCE.read_text())
    nodes = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in NAMES:
            node.decorator_list = []
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in NAMES for t in node.targets):
            nodes.append(node)
    env = dict(html=html, json=json, re=re, asyncio=asyncio, httpx=httpx, validate=validate, HTTPException=HTTPException, SESSIONS={},
               MODEL="m", OLLAMA="http://x", NUM_CTX=8192, KEEP_ALIVE="30m")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), env)
    return env

class LogicTests(unittest.TestCase):
    def setUp(self):
        self.m = load_logic()
        self.s = {"transcript": "Amount due $240\nPay by 15 Nov 2026\nCall billing 555-0142", "checklist": [], "pro_questions": []}
    def test_json(self):
        self.assertEqual(self.m["parse_json"]('```json\n{"a":1}\n```'), {"a":1})
    def test_invalid_json(self):
        with self.assertRaises(Exception): self.m["parse_json"]("bad")
    def test_search(self):
        log=[]
        self.assertIn("$240", self.m["run_tool"](self.s, "find_in_document", {"query":"amount due"}, log))
        self.assertEqual(log[0]["tool"], "find_in_document")
    def test_no_match(self):
        self.assertIn("No matching", self.m["run_tool"](self.s,"find_in_document",{"query":"absent"},[]))
    def test_add_task(self):
        self.m["run_tool"](self.s,"add_checklist_item",{"text":"Call billing","due":"tomorrow"},[])
        self.assertEqual(self.s["checklist"][0]["text"],"Call billing")
    def test_add_question(self):
        self.m["run_tool"](self.s,"add_question_for_professional",{"question":"Is this duplicated?"},[])
        self.assertEqual(len(self.s["pro_questions"]),1)
    def test_bad_tool_args(self):
        self.assertEqual(self.m["run_tool"](self.s,"find_in_document",[],[]),"Invalid tool arguments.")
    def test_unknown_tool(self):
        self.assertEqual(self.m["run_tool"](self.s,"execute_shell",{},[]),"Unknown tool.")
    def test_missing_session(self):
        with self.assertRaises(HTTPException): self.m["get_session"]("missing")
    def test_prompts(self):
        p=self.m["system_prompt"]("Spanish","simple")
        self.assertIn("Spanish",p)
        self.assertIn("untrusted",p)
        self.assertIn("do not diagnose",p)
    def test_structured_retries_schema_error(self):
        responses=iter(['{"a":2}', '{"a":"ok"}'])
        async def fake(*args, **kwargs): return {"content":next(responses)}
        self.m["ollama_chat"]=fake
        schema={"type":"object","properties":{"a":{"type":"string"}},"required":["a"]}
        self.assertEqual(asyncio.run(self.m["structured"]([],schema)),{"a":"ok"})
    def test_structured_fails_closed(self):
        async def fake(*args,**kwargs): return {"content":"bad"}
        self.m["ollama_chat"]=fake
        with self.assertRaises(HTTPException): asyncio.run(self.m["structured"]([],{"type":"object"}))
    def test_export_escapes(self):
        self.s.update(result={"summary":"<script>alert(1)</script>","deadlines":[]})
        self.m["SESSIONS"]["test"]=self.s
        page=asyncio.run(self.m["export"]("test"))
        self.assertIn("&lt;script&gt;",page)
        self.assertNotIn("<script>alert",page)
    def test_quiz_enforces_three_options(self):
        q={"questions":[{"question":"Q","options":["a","b"],"answer_index":0,"explanation":"E"}]*3}
        with self.assertRaises(Exception): validate(q,self.m["QUIZ_SCHEMA"])

    def test_text_schema_drops_transcript(self):
        self.assertNotIn("transcript", self.m["TEXT_SCHEMA"]["properties"])
        self.assertNotIn("transcript", self.m["TEXT_SCHEMA"]["required"])
        self.assertIn("transcript", self.m["ANALYZE_SCHEMA"]["required"])
    def test_ground_ignores_whitespace_and_case(self):
        items=[{"quote":"PAY  by\n15 nov 2026"},{"quote":"invented"},{"quote":"  "}]
        self.assertEqual(self.m["ground"](items,self.s["transcript"]),items[:1])
    def test_help_prompt_has_no_document(self):
        self.assertIn("No document has been analyzed", self.m["HELP_ADDENDUM"])
    def test_ndjson_streams_events_and_errors(self):
        async def worker(emit):
            emit({"t":"token","v":"hi"}); raise self.m["HTTPException"](400,"boom")
        async def collect():
            return [json.loads(x) async for x in self.m["ndjson"](worker)]
        self.assertEqual(asyncio.run(collect()),[{"t":"token","v":"hi"},{"t":"error","v":"boom"}])
    def test_ollama_stream_merges_tokens_and_tool_calls(self):
        lines=[json.dumps({"message":{"content":"Hel"}}),json.dumps({"message":{"content":"lo"}}),
               json.dumps({"message":{"content":"","tool_calls":[{"function":{"name":"x","arguments":{}}}]}})]
        sent=[]
        class Resp:
            def __init__(s,code): s.status_code=code
            async def aread(s): return b"does not support think"
            def raise_for_status(s): raise httpx.HTTPStatusError("bad",request=None,response=None)
            async def aiter_lines(s):
                for l in lines: yield l
        class Ctx:
            def __init__(s,payload): s.payload=payload
            async def __aenter__(s):
                sent.append(dict(s.payload)); return Resp(400 if "think" in s.payload else 200)
            async def __aexit__(s,*a): pass
        class Client:
            def stream(s,method,url,json): return Ctx(json)
        self.m["OLLAMA_CLIENT"]=Client()
        chunks=[]
        msg=asyncio.run(self.m["ollama_chat"]([],on_chunk=chunks.append))
        self.assertEqual(msg["content"],"Hello"); self.assertEqual(chunks,["Hel","lo"])
        self.assertEqual(msg["tool_calls"][0]["function"]["name"],"x")
        self.assertIn("think",sent[0]); self.assertNotIn("think",sent[1])  # retried without think
    def test_checklist_dedupes(self):
        for _ in range(2): self.m["run_tool"](self.s,"add_checklist_item",{"text":"Call billing"},[])
        self.assertEqual(len(self.s["checklist"]),1)

    def test_apply_translation_keeps_quotes_and_rejects_misaligned_lists(self):
        r={"summary":"Pay $240","what_it_means_for_you":["a","b"],"key_numbers":[{"label":"Due","value":"$240","quote":"Amount due $240"}],
           "deadlines":[{"what":"Pay","date":"15 Nov 2026","quote":"Pay by 15 Nov 2026"}],"glossary":[],"questions_to_ask":["q"],"warnings":[]}
        out={"summary":"Pague $240","meaning":["uno"],"number_labels":["Vence"],"deadline_whats":["Pagar"],"glossary":[],
             "questions":["p"],"warnings":[],"checklist":["Llamar","extra"]}
        res=self.m["apply_translation"](r,[{"text":"Call"}],out)
        t=res["result"]
        self.assertEqual(t["summary"],"Pague $240")
        self.assertEqual(t["what_it_means_for_you"],["a","b"])        # wrong length: original kept
        self.assertEqual(t["key_numbers"][0],{"label":"Vence","value":"$240","quote":"Amount due $240"})
        self.assertEqual(t["deadlines"][0]["date"],"15 Nov 2026")
        self.assertEqual(res["checklist"],["Call"])                   # misaligned checklist: original kept
        self.assertEqual(r["summary"],"Pay $240")                     # input not mutated

    def test_speed_estimate_across_families(self):
        f=self.m["speed_estimate"]
        cases={"gemma4:e2b":"fast","gemma4:e4b":"fast","gemma4:12b":"medium","gemma4:26b":"medium","gemma4:31b":"slow",
               "gemma3n:e4b":"fast","gemma3:1b":"fast","gemma3:4b":"fast","gemma3:12b":"medium","gemma3:27b":"medium",
               "gemma2:2b":"fast","gemma2:9b":"medium","gemma2:27b":"medium","gemma3:latest":"fast","gemma3:27b-it-qat":"medium"}
        for tag,exp in cases.items(): self.assertEqual(f(tag),exp,tag)
        self.assertEqual([f("gemma4:e2b",True),f("gemma4:e4b",True),f("gemma4:12b",True),f("gemma3:27b",True)],["medium","medium","slow","slow"])
    def test_model_info_vision_and_size(self):
        i=self.m["model_info"]
        self.assertEqual(i("gemma4:e4b"),{"family":"gemma4","size":4.0,"vision":True})
        self.assertEqual(i("gemma3n:e2b")["size"],2.0)
        self.assertTrue(i("gemma3:4b")["vision"]); self.assertTrue(i("gemma3:27b")["vision"])
        self.assertFalse(i("gemma3:1b")["vision"]); self.assertFalse(i("gemma3:270m")["vision"])
        self.assertFalse(i("gemma2:9b")["vision"])
        self.assertEqual(i("gemma3:latest")["size"],4); self.assertEqual(i("gemma2:latest")["size"],9)
    def test_tools_rejected_once_is_remembered(self):
        sent=[]
        class Resp:
            def __init__(s,code): s.status_code=code
            async def aread(s): return b"registry.ollama.ai/library/gemma3 does not support tools"
            def raise_for_status(s): raise httpx.HTTPStatusError("bad")
            async def aiter_lines(s):
                yield json.dumps({"message":{"content":"ok"}})
        class Ctx:
            def __init__(s,p): s.p=p
            async def __aenter__(s): sent.append(dict(s.p)); return Resp(400 if "tools" in s.p else 200)
            async def __aexit__(s,*a): pass
        class Client:
            def stream(s,m,u,json): return Ctx(json)
        self.m["OLLAMA_CLIENT"]=Client()
        for _ in range(2): self.assertEqual(asyncio.run(self.m["ollama_chat"]([],tools=[{"x":1}]))["content"],"ok")
        self.assertEqual(len(sent),3)           # first call: tools then retry; second call: no wasted retry
        self.assertIn("tools",self.m["UNSUPPORTED"]); self.assertNotIn("tools",sent[2])

if __name__ == "__main__": unittest.main()
