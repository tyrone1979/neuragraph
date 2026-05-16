#!/usr/bin/env python3
"""
BC5CDR Evaluation Script
Compares predicted entities/relations against gold standard.

Usage:
    python experiments/evaluate.py \\
        --gold testsets/bio_ner/test.txt \\
        --pred results/baseline_flair.json \\
        --output results/evaluation_baseline.json

Supports three tasks:
  - Task 1: Chemical NER
  - Task 2: Disease NER  
  - Task 3: CID Relation Extraction
"""
import argparse
import json
import sys
import os
from typing import Dict, List, Set, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from data.data_parser import CIDParser


def normalize_entity(text: str) -> str:
    """Normalize entity text for comparison."""
    return text.lower().strip().rstrip('.,;')


def extract_gold_entities(pubtator_path: str) -> Dict[str, Dict[str, List[str]]]:
    """
    Extract gold entities from PubTator file.
    Returns: {pmid: {'chemicals': [...], 'diseases': [...]}}
    """
    parser = CIDParser(None, None, None)
    docs = parser.parse_pubtator(pubtator_path)
    
    gold = {}
    for doc in docs:
        pmid = doc['pmid']
        chemicals = []
        diseases = []
        
        for ent in doc.get('entities', []):
            ent_type = ent.get('type', '')
            ent_text = ent.get('text', '')
            normalized = normalize_entity(ent_text)
            
            if ent_type == 'Chemical':
                chemicals.append(normalized)
            elif ent_type == 'Disease':
                diseases.append(normalized)
        
        gold[pmid] = {
            'chemicals': list(set(chemicals)),
            'diseases': list(set(diseases))
        }
    
    return gold


def extract_gold_relations(pubtator_path: str) -> Dict[str, Set[Tuple[str, str]]]:
    """
    Extract gold CID relations from PubTator file.
    Returns: {pmid: {(chemical_text, disease_text), ...}}
    """
    parser = CIDParser(None, None, None)
    docs = parser.parse_pubtator(pubtator_path)
    
    gold_rels = {}
    for doc in docs:
        pmid = doc['pmid']
        rels = set()
        
        for rel in doc.get('relations', []):
            if rel.get('type') == 'CID':
                chem_id = rel.get('chemical_id', '')
                disease_id = rel.get('disease_id', '')
                
                # Find entity texts by MESH ID
                chem_text = ''
                dis_text = ''
                for ent in doc.get('entities', []):
                    if ent.get('mesh_id') == chem_id and ent.get('type') == 'Chemical':
                        chem_text = normalize_entity(ent.get('text', ''))
                    if ent.get('mesh_id') == disease_id and ent.get('type') == 'Disease':
                        dis_text = normalize_entity(ent.get('text', ''))
                
                if chem_text and dis_text:
                    rels.add((chem_text, dis_text))
        
        gold_rels[pmid] = rels
    
    return gold_rels


def extract_pred_entities(pred_path: str) -> Dict[str, Dict[str, List[str]]]:
    """Load predicted entities from JSON."""
    with open(pred_path) as f:
        data = json.load(f)
    
    pred = {}
    results = data.get('results', data)  # Handle both formats
    
    for pmid, result in results.items():
        if pmid == 'metadata':
            continue
        pred[pmid] = {
            'chemicals': [normalize_entity(c) for c in result.get('chemicals', [])],
            'diseases': [normalize_entity(d) for d in result.get('diseases', [])]
        }
    
    return pred


def extract_pred_relations(pred_path: str) -> Dict[str, Set[Tuple[str, str]]]:
    """Load predicted relations from JSON."""
    with open(pred_path) as f:
        data = json.load(f)
    
    pred_rels = defaultdict(set)
    relations = data.get('relations', [])
    
    # If relations are stored globally (not per-pmid), distribute them
    if relations and isinstance(relations, list):
        for rel in relations:
            if isinstance(rel, dict):
                chem = normalize_entity(rel.get('chemical', ''))
                dis = normalize_entity(rel.get('disease', ''))
                # We can't map to PMID without context, skip for now
    
    return dict(pred_rels)


def calculate_metrics(gold_set: Set[str], pred_set: Set[str]) -> Dict:
    """Calculate precision, recall, F1."""
    tp = len(gold_set & pred_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        'tp': tp, 'fp': fp, 'fn': fn,
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4)
    }


def evaluate_ner(gold: Dict, pred: Dict, entity_type: str) -> Dict:
    """
    Evaluate NER task.
    Returns micro and macro metrics.
    """
    all_pmids = set(gold.keys()) & set(pred.keys())
    
    # Micro: aggregate all TP/FP/FN
    all_gold = set()
    all_pred = set()
    per_doc_scores = []
    
    for pmid in all_pmids:
        gold_ents = set(gold[pmid].get(entity_type, []))
        pred_ents = set(pred.get(pmid, {}).get(entity_type, []))
        
        # Add PMID prefix for global uniqueness
        all_gold.update(f"{pmid}:{e}" for e in gold_ents)
        all_pred.update(f"{pmid}:{e}" for e in pred_ents)
        
        # Per-doc for macro
        doc_metrics = calculate_metrics(gold_ents, pred_ents)
        per_doc_scores.append(doc_metrics)
    
    micro = calculate_metrics(all_gold, all_pred)
    
    # Macro: average per-doc scores
    if per_doc_scores:
        macro = {
            'precision': round(sum(s['precision'] for s in per_doc_scores) / len(per_doc_scores), 4),
            'recall': round(sum(s['recall'] for s in per_doc_scores) / len(per_doc_scores), 4),
            'f1': round(sum(s['f1'] for s in per_doc_scores) / len(per_doc_scores), 4)
        }
    else:
        macro = {'precision': 0.0, 'recall': 0.0, 'f1': 0.0}
    
    return {
        'micro': {k: v for k, v in micro.items() if k in ('precision', 'recall', 'f1')},
        'macro': macro,
        'num_documents': len(all_pmids),
        'per_document': per_doc_scores[:5]  # Show first 5 as examples
    }


def evaluate_task3_cooccurrence(pubtator_path: str, pred_path: str) -> Dict:
    """
    Task 3: CID Relation Extraction.
    Baseline: chemical-disease co-occurrence in same document.
    """
    parser = CIDParser(None, None, None)
    docs = parser.parse_pubtator(pubtator_path)
    
    with open(pred_path) as f:
        pred_data = json.load(f)
    pred_results = pred_data.get('results', pred_data)
    
    all_tp, all_fp, all_fn = 0, 0, 0
    
    for doc in docs:
        pmid = doc['pmid']
        
        # Gold relations
        gold_rels = set()
        for rel in doc.get('relations', []):
            if rel.get('type') == 'CID':
                # Get entity texts
                chem_id = rel.get('chemical_id', '')
                dis_id = rel.get('disease_id', '')
                
                for ent in doc.get('entities', []):
                    if ent.get('mesh_id') == chem_id and ent.get('type') == 'Chemical':
                        chem_text = normalize_entity(ent.get('text', ''))
                    if ent.get('mesh_id') == dis_id and ent.get('type') == 'Disease':
                        dis_text = normalize_entity(ent.get('text', ''))
                
                try:
                    gold_rels.add((chem_text, dis_text))
                except:
                    pass
        
        # Predicted relations (co-occurrence)
        pred_rels = set()
        doc_pred = pred_results.get(pmid, {})
        for chem in doc_pred.get('chemicals', []):
            for dis in doc_pred.get('diseases', []):
                pred_rels.add((normalize_entity(chem), normalize_entity(dis)))
        
        all_tp += len(gold_rels & pred_rels)
        all_fp += len(pred_rels - gold_rels)
        all_fn += len(gold_rels - pred_rels)
    
    precision = all_tp / (all_tp + all_fp) if (all_tp + all_fp) > 0 else 0.0
    recall = all_tp / (all_tp + all_fn) if (all_tp + all_fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        'micro': {
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1': round(f1, 4),
            'tp': all_tp, 'fp': all_fp, 'fn': all_fn
        }
    }


def main():
    parser = argparse.ArgumentParser(description='Evaluate BC5CDR predictions')
    parser.add_argument('--gold', required=True, help='Gold PubTator file')
    parser.add_argument('--pred', required=True, help='Predictions JSON file')
    parser.add_argument('--output', required=True, help='Output evaluation JSON')
    parser.add_argument('--task', choices=['all', '1', '2', '3'], default='all',
                       help='Which task to evaluate (1=Chemical NER, 2=Disease NER, 3=CID RE)')
    args = parser.parse_args()
    
    print(f"[INFO] Loading gold standard from {args.gold}")
    gold_entities = extract_gold_entities(args.gold)
    
    print(f"[INFO] Loading predictions from {args.pred}")
    pred_entities = extract_pred_entities(args.pred)
    
    results = {}
    
    # Task 1: Chemical NER
    if args.task in ('all', '1'):
        print("[INFO] Evaluating Task 1: Chemical NER")
        results['task1_chemical_ner'] = evaluate_ner(gold_entities, pred_entities, 'chemicals')
        m = results['task1_chemical_ner']['micro']
        print(f"  Micro P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f}")
    
    # Task 2: Disease NER
    if args.task in ('all', '2'):
        print("[INFO] Evaluating Task 2: Disease NER")
        results['task2_disease_ner'] = evaluate_ner(gold_entities, pred_entities, 'diseases')
        m = results['task2_disease_ner']['micro']
        print(f"  Micro P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f}")
    
    # Task 3: CID Relation
    if args.task in ('all', '3'):
        print("[INFO] Evaluating Task 3: CID Relation Extraction")
        results['task3_cid_relation'] = evaluate_task3_cooccurrence(args.gold, args.pred)
        m = results['task3_cid_relation']['micro']
        print(f"  Micro P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f} (TP={m['tp']} FP={m['fp']} FN={m['fn']})")
    
    # Save
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"[DONE] Results saved to {args.output}")


if __name__ == '__main__':
    main()
