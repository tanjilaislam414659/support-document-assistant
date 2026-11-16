"""Format unchanged saved outputs and confirmed narratives; no scoring or inference."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def main():
    h=json.loads((ROOT/"research/results/human-review.original.json").read_bytes())
    lines=["# Saved final evidence and confirmed review","",
        "Curated readable view of existing records only. No new inference, retrieval, labels or scores. The original human annotations remain separate; exact supplied evidence and messages are retained in the linked context projections. Controls are not ordinary retrieval successes.",""]
    for cohort in ("ordinary","gold_evidence_control","genuine_evidence_plus_distractor","distractor_only"):
        records=[r for r in h["records"] if r["context_type"]==cohort]
        if not records:continue
        lines+=["## "+cohort.replace("_"," "),"",""]
        for r in records:
            d=json.loads((ROOT/"research/results/contexts"/(r["context_id"]+".json")).read_bytes())
            lines+=["### "+r["context_id"],"", "**Question:** "+d["question"],"",
                "**Application outcome:** "+d["application_outcome"]+". **Finish reason:** "+str(d["finish_reason"])+".",
                "", "**Exact raw output:**","","~~~json",d["raw_output"],"~~~","",
                "**Confirmed human assessment:** "+r["confirmed_narrative"],"",
                "**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.","",
                "[Full supplied evidence, source mappings and output projection](../research/results/contexts/"+r["context_id"]+".json).",""]
    (ROOT/"docs/saved-evidence.md").write_text("\n".join(lines)+"\n",encoding="utf-8",newline="\n")
if __name__=="__main__":main()
