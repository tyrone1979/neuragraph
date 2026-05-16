#!/usr/bin/env python3
"""
Generate comparison report from evaluation results.

Usage:
    python experiments/generate_report.py \\
        --methods results/eval_llm.json results/eval_baseline.json \\
        --labels "NeuraGraph (GPT-4o)" "Flair HunFlair2" \\
        --output report/bc5cdr_comparison.md

Generates a Markdown report with tables and analysis suitable for publication.
"""
import argparse
import json
import os
import time
from typing import List, Dict


def load_eval(path: str) -> Dict:
    with open(path) as f:
        return json.load(f)


def format_row(task_name: str, results: Dict, avg_key: str = 'micro') -> str:
    """Format a table row for a task."""
    if task_name not in results:
        return ""
    
    m = results[task_name].get(avg_key, {})
    p = m.get('precision', 0.0)
    r = m.get('recall', 0.0)
    f = m.get('f1', 0.0)
    return f"| {p:.3f} | {r:.3f} | {f:.3f} |"


def generate_report(method_paths: List[str], labels: List[str], output_path: str):
    """Generate a publication-ready comparison report."""
    
    evals = [load_eval(p) for p in method_paths]
    
    lines = []
    lines.append("# BC5CDR Pharmacological Evaluation Report")
    lines.append("")
    lines.append(f"**Generated**: {time.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("This report presents a comprehensive evaluation of NeuraGraph on the **BioCreative V CDR (Chemical-Disease Relation)** benchmark, a standard dataset for pharmacological text mining. Three tasks are evaluated:")
    lines.append("")
    lines.append("1. **Task 1 (Chemical NER)**: Identify chemical entities in biomedical abstracts")
    lines.append("2. **Task 2 (Disease NER)**: Identify disease entities in biomedical abstracts")
    lines.append("3. **Task 3 (CID Relation Extraction)**: Extract chemical-induced-disease relations")
    lines.append("")
    
    # Results Table - Micro
    lines.append("## Results (Micro-Averaged)")
    lines.append("")
    lines.append("| Method | Chemical P | Chemical R | Chemical F1 | Disease P | Disease R | Disease F1 | CID P | CID R | CID F1 |")
    lines.append("|--------|------------|------------|-------------|-----------|-----------|------------|-------|-------|--------|")
    
    for label, ev in zip(labels, evals):
        t1 = ev.get('task1_chemical_ner', {}).get('micro', {})
        t2 = ev.get('task2_disease_ner', {}).get('micro', {})
        t3 = ev.get('task3_cid_relation', {}).get('micro', {})
        
        row = f"| {label} "
        row += f"| {t1.get('precision', 0):.3f} | {t1.get('recall', 0):.3f} | {t1.get('f1', 0):.3f} "
        row += f"| {t2.get('precision', 0):.3f} | {t2.get('recall', 0):.3f} | {t2.get('f1', 0):.3f} "
        row += f"| {t3.get('precision', 0):.3f} | {t3.get('recall', 0):.3f} | {t3.get('f1', 0):.3f} |"
        lines.append(row)
    
    lines.append("")
    
    # Results Table - Macro
    lines.append("## Results (Macro-Averaged)")
    lines.append("")
    lines.append("| Method | Chemical F1 | Disease F1 |")
    lines.append("|--------|-------------|------------|")
    
    for label, ev in zip(labels, evals):
        t1 = ev.get('task1_chemical_ner', {}).get('macro', {})
        t2 = ev.get('task2_disease_ner', {}).get('macro', {})
        lines.append(f"| {label} | {t1.get('f1', 0):.3f} | {t2.get('f1', 0):.3f} |")
    
    lines.append("")
    
    # Per-document analysis
    lines.append("## Per-Document Analysis")
    lines.append("")
    lines.append("Distribution of per-document F1 scores for NER tasks:")
    lines.append("")
    
    for label, ev in zip(labels, evals):
        lines.append(f"### {label}")
        lines.append("")
        
        for task_key in ['task1_chemical_ner', 'task2_disease_ner']:
            task_name = 'Chemical NER' if 'chemical' in task_key else 'Disease NER'
            per_doc = ev.get(task_key, {}).get('per_document', [])
            if per_doc:
                f1s = [d['f1'] for d in per_doc]
                lines.append(f"**{task_name}**: "
                           f"mean={sum(f1s)/len(f1s):.3f}, "
                           f"min={min(f1s):.3f}, "
                           f"max={max(f1s):.3f}, "
                           f"docs={len(f1s)}")
        lines.append("")
    
    # Discussion
    lines.append("## Discussion")
    lines.append("")
    lines.append("### Key Findings")
    lines.append("")
    
    # Compare methods
    if len(evals) >= 2:
        llm = evals[0]
        baseline = evals[1]
        
        llm_chem_f1 = llm.get('task1_chemical_ner', {}).get('micro', {}).get('f1', 0)
        base_chem_f1 = baseline.get('task1_chemical_ner', {}).get('micro', {}).get('f1', 0)
        
        lines.append(f"1. **Chemical NER**: {labels[0]} achieves F1={llm_chem_f1:.3f} "
                      f"vs {labels[1]} F1={base_chem_f1:.3f}. "
                      f"{'LLM' if llm_chem_f1 > base_chem_f1 else 'Baseline'} performs better.")
        
        llm_dis_f1 = llm.get('task2_disease_ner', {}).get('micro', {}).get('f1', 0)
        base_dis_f1 = baseline.get('task2_disease_ner', {}).get('micro', {}).get('f1', 0)
        
        lines.append(f"2. **Disease NER**: {labels[0]} achieves F1={llm_dis_f1:.3f} "
                      f"vs {labels[1]} F1={base_dis_f1:.3f}.")
        
        llm_cid = llm.get('task3_cid_relation', {}).get('micro', {})
        if llm_cid:
            lines.append(f"3. **CID Relation**: {labels[0]} achieves F1={llm_cid.get('f1', 0):.3f} "
                          f"(P={llm_cid.get('precision', 0):.3f}, R={llm_cid.get('recall', 0):.3f}).")
    
    lines.append("")
    lines.append("### Advantages of NeuraGraph")
    lines.append("")
    lines.append("- **Zero-shot capability**: No domain-specific training data required")
    lines.append("- **Unified platform**: NER and RE tasks integrated in a single workflow")
    lines.append("- **Configurable pipeline**: Workflow graph can be edited to adjust processing steps")
    lines.append("- **Extensible**: New agents and tools can be added without code changes")
    lines.append("")
    lines.append("### Limitations")
    lines.append("")
    lines.append("- **Runtime**: LLM-based approaches are slower than fine-tuned models (API latency)")
    lines.append("- **Precision**: Entity boundaries may be less precise than specialized BioNER models")
    lines.append("- **Cost**: API calls incur costs; local deployment (Ollama) can mitigate this")
    lines.append("")
    
    # Future Work
    lines.append("## Future Work")
    lines.append("")
    lines.append("1. **Local LLM deployment**: Use Ollama with domain-adapted models to reduce latency and cost")
    lines.append("2. **Few-shot prompting**: Include example entities in prompts to improve accuracy")
    lines.append("3. **Ensemble methods**: Combine LLM and Flair predictions for higher F1")
    lines.append("4. **Additional benchmarks**: Evaluate on NLM-Chem, BC7-LitCovid datasets")
    lines.append("")
    
    # References
    lines.append("## References")
    lines.append("")
    lines.append("1. Wei CH, et al. (2015). Overview of the BioCreative V Chemical Disease Relation (CDR) Task. *Proceedings of BioCreative V*.")
    lines.append("2. Sanger Laboratory (2021). HunFlair2: A State-of-the-Art Biomedical Named Entity Recognition Tool. *Bioinformatics*.")
    lines.append("")
    
    # Write
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"[DONE] Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate evaluation comparison report')
    parser.add_argument('--methods', nargs='+', required=True, help='Evaluation JSON files')
    parser.add_argument('--labels', nargs='+', required=True, help='Method labels')
    parser.add_argument('--output', required=True, help='Output markdown file')
    args = parser.parse_args()
    
    if len(args.methods) != len(args.labels):
        print("[ERROR] Number of methods and labels must match")
        return
    
    generate_report(args.methods, args.labels, args.output)


if __name__ == '__main__':
    main()
