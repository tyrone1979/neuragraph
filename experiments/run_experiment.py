#!/usr/bin/env python3
"""
End-to-end BC5CDR Experiment Runner for NeuraGraph

This script runs a complete evaluation experiment:
1. Loads a workflow configuration
2. Runs it on BC5CDR test data batch-by-batch
3. Collects results
4. Evaluates against gold standard
5. Generates report

Usage:
    # Method 1: Run NeuraGraph experiment (requires Flask server)
    python experiments/run_experiment.py \\
        --workflow bio_ner_graph \\
        --dataset testsets/bio_ner/test.txt \\
        --output results/neuragraph_results.json \\
        --api-url http://localhost:5001

    # Method 2: Run baseline
    python experiments/run_experiment.py \\
        --baseline \\
        --dataset testsets/bio_ner/test.txt \\
        --output results/baseline_results.json

    # Method 3: Evaluate existing results
    python experiments/run_experiment.py \\
        --evaluate \\
        --gold testsets/bio_ner/test.txt \\
        --pred results/neuragraph_results.json \\
        --output results/eval_neuragraph.json

    # Method 4: Full pipeline (run + evaluate + report)
    python experiments/run_experiment.py \\
        --full \\
        --workflow bio_ner_graph \\
        --dataset testsets/bio_ner/test.txt \\
        --output-prefix results/bc5cdr \\
        --api-url http://localhost:5001
"""
import argparse
import json
import sys
import os
import time
import requests
from typing import Dict, List
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from service.dataset.data_parser import CIDParser


def parse_document_entities(doc: Dict) -> Dict:
    """Extract entities from a document into NeuraGraph state format."""
    title = doc.get('title', '')
    abstract = doc.get('abstract', '')
    full_text = f"{title} {abstract}".strip()
    
    return {
        'pmid': doc['pmid'],
        'expected_entities': full_text,
        'title': title,
        'abstract': abstract
    }


def run_via_api(workflow_id: str, state: Dict, api_url: str) -> Dict:
    """Run a single document through NeuraGraph API."""
    try:
        resp = requests.post(
            f"{api_url}/api/graph/run",
            json={'graph_id': workflow_id, 'state': state},
            timeout=120
        )
        if resp.status_code == 200:
            return resp.json().get('state', {})
        else:
            print(f"  [WARN] API error {resp.status_code}: {resp.text[:200]}")
            return {}
    except Exception as e:
        print(f"  [WARN] Request failed: {e}")
        return {}


def extract_entities_from_state(state: Dict) -> Dict:
    """Extract predicted entities from NeuraGraph state."""
    # The bio_ner agent outputs entities to 'expected_entities' or similar fields
    # This depends on the actual workflow output format
    
    result = {'chemicals': [], 'diseases': []}
    
    # Try different possible output fields
    output = state.get('expected_entities', '')
    if isinstance(output, str):
        # Try to parse JSON output
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                result['chemicals'] = parsed.get('chemicals', [])
                result['diseases'] = parsed.get('diseases', [])
        except (json.JSONDecodeError, TypeError):
            pass
    elif isinstance(output, dict):
        result['chemicals'] = output.get('chemicals', [])
        result['diseases'] = output.get('diseases', [])
    
    # Fallback: check other state fields
    for key in ['chemicals', 'chemical', ' Chemical', 'Chemical']:
        if key in state and isinstance(state[key], list):
            result['chemicals'] = state[key]
    for key in ['diseases', 'disease', ' Disease', 'Disease']:
        if key in state and isinstance(state[key], list):
            result['diseases'] = state[key]
    
    return result


def run_neuragraph_experiment(workflow_id: str, dataset_path: str, api_url: str, 
                               output_path: str, limit: int = None):
    """Run full NeuraGraph experiment on BC5CDR dataset."""
    print(f"[INFO] Loading dataset: {dataset_path}")
    parser = CIDParser(None, None, None)
    docs = parser.parse_pubtator(dataset_path)
    
    if limit:
        docs = docs[:limit]
    
    print(f"[INFO] Running workflow '{workflow_id}' on {len(docs)} documents")
    print(f"[INFO] API endpoint: {api_url}")
    
    results = {}
    start_time = time.time()
    
    for i, doc in enumerate(docs):
        pmid = doc['pmid']
        print(f"[{i+1}/{len(docs)}] Processing PMID {pmid}...", end=' ')
        
        state = parse_document_entities(doc)
        output_state = run_via_api(workflow_id, state, api_url)
        entities = extract_entities_from_state(output_state)
        
        results[pmid] = entities
        print(f"C={len(entities['chemicals'])} D={len(entities['diseases'])}")
        
        # Rate limiting
        time.sleep(0.5)
    
    elapsed = time.time() - start_time
    
    # Save results
    output = {
        'metadata': {
            'method': f'neuragraph_{workflow_id}',
            'dataset': os.path.basename(dataset_path),
            'num_documents': len(docs),
            'runtime_seconds': round(elapsed, 2),
            'api_url': api_url,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
        },
        'results': results
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n[DONE] Results saved to {output_path}")
    print(f"[STATS] Runtime: {elapsed:.1f}s ({elapsed/len(docs):.1f}s/doc)")
    return output_path


def run_baseline(dataset_path: str, output_path: str):
    """Run Flair baseline."""
    print("[INFO] Running Flair HunFlair2 baseline")
    from experiments.run_baseline_flair import main as baseline_main
    
    # Build args
    class Args:
        input = dataset_path
        output = output_path
        batch_size = 32
        limit = None
    
    import experiments.run_baseline_flair
    sys.argv = ['run_baseline_flair.py', '--input', dataset_path, '--output', output_path]
    baseline_main()


def run_evaluation(gold_path: str, pred_path: str, output_path: str):
    """Run evaluation."""
    print(f"[INFO] Evaluating: {pred_path}")
    from experiments.evaluate import main as eval_main
    
    sys.argv = ['evaluate.py', '--gold', gold_path, '--pred', pred_path, '--output', output_path, '--task', 'all']
    eval_main()


def generate_comparison_report(eval_paths: List[str], labels: List[str], output_path: str):
    """Generate comparison report."""
    print("[INFO] Generating comparison report")
    from experiments.generate_report import generate_report
    generate_report(eval_paths, labels, output_path)


def main():
    parser = argparse.ArgumentParser(description='BC5CDR Experiment Runner')
    
    # Modes
    parser.add_argument('--full', action='store_true', help='Run full pipeline')
    parser.add_argument('--baseline', action='store_true', help='Run baseline only')
    parser.add_argument('--evaluate', action='store_true', help='Evaluate existing predictions')
    
    # Inputs
    parser.add_argument('--workflow', default='bio_ner_graph', help='Workflow ID for NeuraGraph')
    parser.add_argument('--dataset', default='testsets/bio_ner/test.txt', help='BC5CDR PubTator file')
    parser.add_argument('--gold', help='Gold standard (for evaluation)')
    parser.add_argument('--pred', help='Predictions (for evaluation)')
    
    # API
    parser.add_argument('--api-url', default='http://localhost:5001', help='NeuraGraph API URL')
    
    # Outputs
    parser.add_argument('--output', help='Output path for predictions')
    parser.add_argument('--output-prefix', default='results/bc5cdr', help='Prefix for full pipeline outputs')
    parser.add_argument('--limit', type=int, help='Limit documents (for testing)')
    
    args = parser.parse_args()
    
    if args.full:
        # Full pipeline: run both methods + evaluate + report
        prefix = args.output_prefix
        
        # 1. Run NeuraGraph
        ng_pred = f"{prefix}_neuragraph.json"
        run_neuragraph_experiment(args.workflow, args.dataset, args.api_url, ng_pred, args.limit)
        
        # 2. Run Baseline
        base_pred = f"{prefix}_baseline.json"
        run_baseline(args.dataset, base_pred)
        
        # 3. Evaluate both
        ng_eval = f"{prefix}_eval_neuragraph.json"
        base_eval = f"{prefix}_eval_baseline.json"
        run_evaluation(args.dataset, ng_pred, ng_eval)
        run_evaluation(args.dataset, base_pred, base_eval)
        
        # 4. Generate report
        report_path = f"{prefix}_report.md"
        generate_comparison_report([ng_eval, base_eval], 
                                    ['NeuraGraph (LLM)', 'Flair HunFlair2'],
                                    report_path)
        
        print(f"\n{'='*60}")
        print(f"ALL DONE! Report: {report_path}")
        print(f"{'='*60}")
    
    elif args.baseline:
        output = args.output or 'results/baseline_results.json'
        run_baseline(args.dataset, output)
    
    elif args.evaluate:
        if not args.gold or not args.pred:
            print("[ERROR] --evaluate requires --gold and --pred")
            return
        output = args.output or 'results/evaluation.json'
        run_evaluation(args.gold, args.pred, output)
    
    else:
        # Default: run NeuraGraph experiment
        output = args.output or 'results/neuragraph_results.json'
        run_neuragraph_experiment(args.workflow, args.dataset, args.api_url, output, args.limit)


if __name__ == '__main__':
    main()
