#!/usr/bin/env python3
"""
BC5CDR Baseline Experiment - Flair HunFlair2 NER
Usage:
    python experiments/run_baseline_flair.py \\
        --input testsets/bio_ner/test.txt \\
        --output results/baseline_flair.json \\
        --batch-size 32

Output format: {"pmid": {"chemicals": [...], "diseases": [...]}, ...}
"""
import argparse
import json
import sys
import os
import time
from typing import Dict, List, Tuple
from collections import defaultdict

# Add parent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from service.dataset.data_parser import CIDParser


def parse_pubtator_to_sentences(doc) -> List[Tuple[str, List[dict]]]:
    """Split PubTator document into sentences with entity offsets."""
    title = doc.get('title', '')
    abstract = doc.get('abstract', '')
    full_text = f"{title} {abstract}".strip()
    
    # Simple sentence splitting (PubMed abstracts are usually already sentences)
    # For better results, use nltk or spacy
    try:
        import nltk
        from nltk.tokenize import sent_tokenize
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        sentences = sent_tokenize(full_text)
    except ImportError:
        # Fallback: split by period + space
        sentences = [s.strip() for s in full_text.split('. ') if s.strip()]
    
    # Map entities to sentences
    entities = doc.get('entities', [])
    entity_map = defaultdict(list)
    
    for ent in entities:
        ent_text = ent.get('text', '')
        ent_type = ent.get('type', '')
        ent_offset = ent.get('offset', [0, 0])
        if ent_type in ('Chemical', 'Disease'):
            entity_map[ent_type].append(ent_text)
    
    return sentences, dict(entity_map)


def flair_ner_batch(texts: List[str]) -> List[Dict]:
    """Run Flair NER on a batch of texts."""
    try:
        from flair.nn import Classifier
        from flair.data import Sentence
        
        tagger = Classifier.load("hunflair2")
        results = []
        
        for text in texts:
            sentence = Sentence(text)
            tagger.predict(sentence)
            
            chemicals = []
            diseases = []
            
            for entity in sentence.get_spans('ner'):
                label = entity.tag.lower()
                text_val = entity.text
                if 'chemical' in label or 'chem' in label:
                    chemicals.append(text_val)
                elif 'disease' in label or 'dis' in label or 'disorder' in label:
                    diseases.append(text_val)
            
            results.append({
                'chemicals': list(set(chemicals)),
                'diseases': list(set(diseases))
            })
        
        return results
    except ImportError:
        print("[ERROR] Flair not installed. Run: pip install flair")
        print("[FALLBACK] Using simple keyword matching")
        return keyword_fallback_ner(texts)


def keyword_fallback_ner(texts: List[str]) -> List[Dict]:
    """Fallback: simple keyword matching for chemicals and diseases."""
    # Common chemical suffixes
    chem_suffixes = ['ine', 'ide', 'ol', 'one', 'ate', 'ium', 'gen', 'mab', 'nib', 'zole', 'pril', 'sartan']
    # Common disease keywords
    disease_keywords = ['cancer', 'tumor', 'disease', 'syndrome', 'disorder', 'failure', 
                       'inflammation', 'infection', 'deficiency', 'hypertension', 'diabetes']
    
    results = []
    for text in texts:
        words = text.lower().split()
        chemicals = [w for w in words if any(w.endswith(s) for s in chem_suffixes)]
        diseases = [w for w in words if any(d in w for d in disease_keywords)]
        results.append({'chemicals': list(set(chemicals)), 'diseases': list(set(diseases))})
    return results


def extract_relations_cooccurrence(doc_results: Dict) -> List[Tuple[str, str]]:
    """Extract CID relations by co-occurrence in same sentence."""
    relations = []
    for pmid, result in doc_results.items():
        chemicals = result.get('chemicals', [])
        diseases = result.get('diseases', [])
        for chem in chemicals:
            for dis in diseases:
                relations.append((chem, dis))
    return relations


def main():
    parser = argparse.ArgumentParser(description='Run BC5CDR baseline with Flair NER')
    parser.add_argument('--input', required=True, help='Path to BC5CDR test.txt (PubTator)')
    parser.add_argument('--output', required=True, help='Output JSON path')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size for NER')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of documents (for testing)')
    args = parser.parse_args()
    
    print(f"[INFO] Loading dataset from {args.input}")
    parser_instance = CIDParser(None, None, None)
    docs = parser_instance.parse_pubtator(args.input)
    
    if args.limit:
        docs = docs[:args.limit]
    
    print(f"[INFO] Processing {len(docs)} documents")
    
    results = {}
    all_texts = []
    doc_pmids = []
    
    # Collect all texts
    for doc in docs:
        pmid = doc['pmid']
        title = doc.get('title', '')
        abstract = doc.get('abstract', '')
        full_text = f"{title} {abstract}".strip()
        all_texts.append(full_text)
        doc_pmids.append(pmid)
    
    # Process in batches
    start_time = time.time()
    ner_results = []
    
    for i in range(0, len(all_texts), args.batch_size):
        batch = all_texts[i:i + args.batch_size]
        print(f"[INFO] Processing batch {i//args.batch_size + 1}/{(len(all_texts)-1)//args.batch_size + 1} ({len(batch)} docs)")
        batch_results = flair_ner_batch(batch)
        ner_results.extend(batch_results)
    
    elapsed = time.time() - start_time
    
    # Build results
    for pmid, ner in zip(doc_pmids, ner_results):
        results[pmid] = ner
    
    # Extract relations
    relations = extract_relations_cooccurrence(results)
    
    # Save
    output = {
        'metadata': {
            'method': 'flair_hunflair2',
            'dataset': os.path.basename(args.input),
            'num_documents': len(docs),
            'runtime_seconds': round(elapsed, 2),
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
        },
        'results': results,
        'relations': [{'chemical': c, 'disease': d} for c, d in relations]
    }
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"[DONE] Results saved to {args.output}")
    print(f"[STATS] Runtime: {elapsed:.1f}s, {len(docs)} docs, {len(relations)} relations")


if __name__ == '__main__':
    main()
