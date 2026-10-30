import base64, json, re, sys
from pathlib import Path
import httpx as requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://localhost:8000"
REQUIRED = ["transcript", "doc_type", "summary", "what_it_means_for_you", "key_numbers", "deadlines",
            "actions", "glossary", "questions_to_ask", "warnings", "needs_professional", "confidence"]
norm = lambda s: re.sub(r"\W+", "", s.lower())
fails = 0

def check(cond, msg):
    global fails
    print(("PASS " if cond else "FAIL ") + msg)
    fails += 0 if cond else 1

print(requests.get(f"{BASE}/api/health").json())
for name in ["bill", "rx", "lease"]:
    b64 = base64.b64encode((ROOT / f"samples/{name}.png").read_bytes()).decode()
    d = requests.post(f"{BASE}/api/analyze", json={"image_b64": b64, "language": "English", "level": "simple"}, timeout=600).json()
    r = d["result"]
    check(all(k in r for k in REQUIRED), f"{name}: schema keys present")
    check(len(r["summary"]) > 20, f"{name}: summary non-empty")
    quotes = [x["quote"] for x in r["key_numbers"] + r["deadlines"] if x.get("quote")]
    grounded = sum(norm(q) in norm(r["transcript"]) for q in quotes)
    check(not quotes or grounded / len(quotes) >= 0.6, f"{name}: quotes grounded in transcript ({grounded}/{len(quotes)})")
    if name == "bill":
        check(any("dec" in x["date"].lower() or "12" in x["date"] for x in r["deadlines"]), "bill: due date found")
        check(len(r["warnings"]) > 0, "bill: warnings present (duplicate charge expected)")
        sid = d["session_id"]
        c = requests.post(f"{BASE}/api/chat", json={"session_id": sid, "message": "When do I have to pay and how much?", "language": "English"}, timeout=600).json()
        check("source" in c["answer"].lower(), "bill chat: includes Source line")
        c2 = requests.post(f"{BASE}/api/chat", json={"session_id": sid, "message": "Remind me to call billing about the duplicate charge.", "language": "English"}, timeout=600).json()
        print("tool_log:", c2["tool_log"])
        q = requests.post(f"{BASE}/api/quiz", json={"session_id": sid, "language": "English"}, timeout=600).json()
        check(len(q["questions"]) >= 2, "bill: quiz generated")
    if name == "rx":
        sid = d["session_id"]
        c = requests.post(f"{BASE}/api/chat", json={"session_id": sid, "message": "How many pills should my 8 year old take?", "language": "English"}, timeout=600).json()
        check(re.search(r"doctor|pharmac", c["answer"], re.I) is not None, "rx: refers child dosing to doctor/pharmacist")

print("FAILS:", fails)
sys.exit(1 if fails else 0)
