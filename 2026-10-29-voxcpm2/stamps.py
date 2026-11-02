import sys
from funasr import AutoModel
m = AutoModel(model="paraformer-zh", disable_update=True)
for p in sys.argv[1:]:
    r = m.generate(input=p)[0]
    print(p.split("/")[-1], " ".join(f"{t}@{a/1000:.2f}-{b/1000:.2f}" for t, (a, b) in zip(r["text"].split(" "), r["timestamp"])), flush=True)
