import re
import urllib.request

url = (
    "http://127.0.0.1:5001/exp/new?"
    "runner_id=wf_cid_ner_llm_eval&runner_type=graph&runner_display=test&filename=cid_dev_2samples.csv"
)
html = urllib.request.urlopen(url, timeout=10).read().decode("utf-8", "replace")
m = re.search(r"const data = (\[.*?\]);", html, re.S)
print("data:", (m.group(1)[:400] if m else "NO DATA"))
rid = re.search(r'id="runnerId" value="([^"]*)"', html)
print("runnerId:", rid.group(1) if rid else "missing")
print("old bug in page:", "datasetSelect.innerHTML" in html)
