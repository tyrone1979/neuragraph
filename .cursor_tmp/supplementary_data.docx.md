**Author:** 磊 赵

# Supplementary Material

## 1. Software architecture

NeuraGraph adopts a three‑layer architecture, as illustrated in Fig. 1. The Presentation Layer provides a browser-based visual editor for drag-and-drop workflow assembly with real-time validation. The Service Layer, built on LangGraph, extends the core orchestrator with custom static analysis for input inference and subgraph validation, and includes native parsers for biomedical benchmarks (CDR, ChemDisGene) to eliminate manual preprocessing. The Persistence Layer uses file-based JSON storage to serialize all experiment artifacts (workflow config, intermediate outputs, metrics), each tagged with a unique dependency hash for exact reproducibility.

Fig. 1. High-level architecture of NeuraGraph, illustrating the three-layer design: Presentation Layer (browser-based visual interface), Service Layer (Flask API, configuration management, plugins, and LangGraph orchestration), and Persistence Layer (in-memory and file-based state and data storage).

## 2. Core Features Implementation

Feature 1 Automatic input inference (Algorithm 1). Given a directed graph G= (V, E) where each node declares its inputs and outputs, NeuraGraph computes the minimal set of external inputs required to invoke G. This guarantees that every data dependency is satisfied before execution.

Feature 2 Recursive subgraph (Algorithm 2). Any workflow graph can be encapsulated as a SUB-type agent and reused inside another graph. The engine recursively invokes the subgraph on each element of an input list and dynamically aggregates outputs. This enables hierarchical composition (e.g., a “sentence-level NER” subgraph used inside a document-level RE workflow).

Feature 3 Plugin Development. The plugin system in NeuraGraph is designed to seamlessly integrate custom, domain‑specific functionalities—such as pre‑trained local models—into agents and tools. Plugin development follows a lightweight, standardized pattern: a new plugin must inherit from the base `Plugin` class and implement a load() method that returns a dictionary of key‑value pairs. These pairs expose the plugin’s capabilities to the runtime environment.

Feature 5 Evaluation. After execution, NeuraGraph automatically computes standard evaluation metrics, including precision (P), recall (R), and F1-score at both micro- and macro-average levels when ground-truth annotations are provided. These metrics are derived by comparing the  outputs against the  ground-truth labels, calculated as follows:

where denotes the number of correct predictions (true positives),  represents all items predicted, and represents all items in the ground truth.

Micro-averaged metrics aggregate counts over all test instances before computing the ratios:

Macro-averaged metrics first compute precision and recall for each instance and then take the arithmetic mean:

where N denotes the number of instances and , , , are the instance-specific values obtained from Eq. (1).

Feature 6 a dedicated LLM‑based reporting agent. The reporting agent processes the raw experiment results along with the persisted JSON result file to generate a comprehensive, structured Markdown report. This report synthesizes quantitative outcomes and qualitative insights. 

## 3. Illustrative examples

### 3.1. An End-to-End Workflow for NER

Dataset Preparation: The workflow was evaluated using the BioCreative V Chemical-Disease Relations (CDR) corpus, a benchmark dataset for biomedical named entity recognition. The relevant dataset statistics are summarized in Table S1.

Table S1. Statistics of the benchmark datasets used for evaluation.

Agent Design: Four specialized agents and one subgraph were constructed to perform sentence-level NER. Their configurations are listed in Table S2.

Table S2. Agent specifications for the NER workflow.

Workflow Graph Design: The agents were assembled into the directed graph shown in Fig. S2. The graph begins with sentence splitting, followed by a sentence-level iteration subgraph that applies the Flair NER agent to each sentence. The extracted entities are then compared with ground-truth annotations to compute performance metrics.

Fig. S2. Workflow graph for the NER task, illustrating the data flow from text input through sentence splitting, iterative NER, and final metric calculation.

Table S3 details the source code line counts of each node in the NER task implemented by NeuraGraph.

Table 3. Source code lines of NeuraGraph for NER task

Table S4 presents the source code line counts of the Custom Python implementation for the same NER task, with a total of 302 lines of code. 

Table S4. Source lines of Custom python for NER task

Experiment Execution and Evaluation Report: The workflow was executed on the CDR test set. Upon completion, the built-in LLM-based analysis agent automatically generated the structured evaluation report presented in Fig. S3, which includes quantitative performance summaries, qualitative observations, and actionable recommendations.

Fig. S3. Automatically generated evaluation report, detailing micro- and macro-averaged precision, recall, and F1-score, along with a performance analysis and interpretation.

Structured Output and Persistence：Upon execution, NeuraGraph automatically persists the complete, structured results for each test instance as a local JSON file, which captures:

Input Metadata: The original text (text) and its sentence-segmented form (sentences).

Entity Ground Truth: The expected chemical and disease entities 

Model Predictions: The corresponding entities extracted by the workflow (predicted).

Evaluation Metrics: Instance-level precision, recall, F1-score, and raw counts of true/false positives and negatives (metrics).

This structured persistence ensures full reproducibility, facilitates downstream error analysis, and provides a transparent record of the model's performance on each individual sample.

### 3.2. A Workflow for Chemical-Induced-Disease Relation Extraction

Data preparation: The workflow was validated on the BioCreative V Chemical-Disease Relations (CDR) corpus, a benchmark dataset for binary relation extraction. The relevant subset statistics are provided in Table S5.

Table S5. Statistics of the benchmark datasets used for evaluation.

Agent Design: Six agents—including one LLM-based verifier, four programmatic agents, and one iteration subgraph—were designed to implement the relation-extraction pipeline. Their specifications are listed in Table S6.

Table S6. Agent specifications for the relation-extraction workflow.

Workflow Design: The agents were assembled into the directed graph shown in Fig. 4. The pipeline begins by generating candidate chemical-disease pairs, then iteratively verifies each pair using the LLM-based relationship-verification agent. Verified relations are linked to standard identifiers and finally evaluated against ground-truth annotations.

Fig. 4. Workflow graph for the chemical-induced-disease relation-extraction task, illustrating the flow from entity-pair generation through iterative verification, entity linking, and performance evaluation.

Table S7 presents the source code line counts of each node in the chemical-induced disease relation extraction (RE) task implemented by NeuraGraph. 

Table S7. Source code lines of NeuraGraph for RE task

Table S8 details the source code line counts of the Custom Python implementation for the same chemical-induced disease RE task.

Table S8. Source code lines of Custom Python for RE task

Table S9 provides the source code line counts of the Dify Tool for both NER and RE tasks, serving as an additional comparison benchmark.

Table S9. Source lines of Dify Tool for NER and RE

Experiment Execution and Evaluation Report: The relation-extraction workflow was executed on the CDR test set following the same experimental protocol described in Section 3.1. Upon completion, the system automatically computed detailed performance metrics for each of the 20 test instances, as summarized in the Table S10.

Table S10. Per-instance performance metrics for the chemical-induced-disease relation-extraction task.

NOTE: True Positives (TP): The number of chemical‑disease entity pairs that were correctly predicted as exhibiting a "chemical‑induces‑disease" relation according to the ground‑truth annotations. False Positives (FP): The number of entity pairs that were incorrectly predicted as having the target relation when no such relation exists in the ground truth. False Negatives (FN): The number of entity pairs that were incorrectly predicted as not having the target relation when such a relation does exist in the ground truth.


### Table 1

| Algorithm 1: Automatic input inference | Algorithm 1: Automatic input inference |
| Input: graph identifier gid | Input: graph identifier gid |
| Output: A sorted list of global input variable names | Output: A sorted list of global input variable names |
| Steps: | Steps: |
| 1 | Load the graph metadata to obtain the list of node list . |
| 2 | Initialize three sets: , , |
| 3 | For each node  (index  from to ):
a. Load the agent metadata  .
b. If  defines an output field , add  to .
c. If = 0, add all inputs of  to ; otherwise, add all its inputs of   to . |
| 4 | Compute the uncovered inputs of non‑first nodes:
 . |
| 5 | The global input set is:  . |
| 6 | Return sort (). |


### Table 2

| Algorithm 2: Recursive Subgraph Invocation(_call_agent) | Algorithm 2: Recursive Subgraph Invocation(_call_agent) |
| Input: Agent identifier ; execution state | Input: Agent identifier ; execution state |
| Output: a partial state update | Output: a partial state update |
| Steps: | Steps: |
| 1 | Load the Agent metadata |
| 2 | Type Check: if : Return |
| 3 | Subgraph Handling ():
a. Subgraph Load: . 
For each node , its execution function is constructed by calling , thereby defining the recursive structure.
b. Extract inputs: Let .
c. Iteration subgraph execution: For each  in 
State Injection: .
Recursive Invocation: .
This invocation recursively triggers  for each node in the subgraph.
Output Extraction: |
| 4 | Dynamic Aggregation: Let  
For each output v: |
| 5 | Return: |


### Table 3

| Dataset Name | # Test set | Entity Labels |
| CDR | 500 | Chemical, Disease |


### Table 4

| Agent Name | Type | Description | Inputs | Outputs |
| Sentence split | LLM | Splits input text into a list of sentences using an LLM (Mistral‑7B) | article text | sentences |
| Map source field to target field | PGM | Maps the ground‑truth field to the format required by downstream agents | the ground‑truth field | expected 
entities |
| Sentence-level iteration | SUB | A subgraph that iterates over each sentence to apply the Flair NER agent | sentence, labels | predicted 
entities |
| Flair NER | PGM | Executes NER using a local Flair model (hunflair2) | sentence, labels | predicted 
entities |
| Performance metrics calculation | PGM | Computes precision, recall, and F1-score by comparing predicted and expected entities | predicted and 
expected entities | metrics |


### Table 5

| Node | Lines |
| Map source field to target field | 1 |
| Sentence split | 0 |
| Flair NER | 15 |
| Performance metrics calculation | 2 |
| Total | 18 |


### Table 6

| File | Lines |
| custom_python_ner | 63 |
| data parser | 141 |
| Data loader | 30 |
| Performance metrics calculation | 68 |
| Total | 302 |


### Table 7

| Dataset Name | # Test set | Relation Type |
| CDR | 20 | Chemical-induces-Disease |


### Table 8

| Agent Name | Type | Description | Inputs | Outputs |
| Create entity pairs | PGM | Generates candidate chemical-disease entity pairs from pre-extracted entities | entities | entity pairs |
| Map source field to target field | PGM | Maps the ground-truth relation field to the format required for evaluation | the ground‑truth field | expected 
relations |
| Iteration for relation verification | SUB | A subgraph that iterates over each candidate entity pair to perform the LLM-based verification | entity pairs, article text, entity link dictionary | predicted relations |
| Relationship verification | LLM | Uses a large language model (GPT-4o) to verify whether a given entity pair exhibits a “chemical-induces-disease” relation | article text, head and tail entity pair | verification result |
| Entity link and map result for metrics | PGM | Links verified entity pairs to standardized identifiers (e.g., MeSH) and formats the output for metric calculation | entity pair, entity link dictionary, result | predicted relations |
| Performance metrics calculation | PGM | Computes precision, recall, and F₁‑score by comparing predicted and expected relations | predicted, expected relations | metrics |


### Table 9

| Node | Lines |
| Create entity pairs | 11 |
| Map source field to target field | 1 |
| Relationship verification | 0 |
| Entity link and map result to pair | 2 |
| Performance metrics calculation | 2 |
| Total | 16 |


### Table 10

| File | Lines |
| custom_python_re | 68 |
| data parser | 141 |
| Data loader | 30 |
| Performance metrics calculation | 68 |
| Total | 307 |


### Table 11

| File | Lines |
| Dify_tools_ner | 101 |
| Dify_tools_re | 149 |


### Table 12

| Article No | Precision | Recall | F1 | # True Positives (TP) | # False Positives (FP) | # False Negatives (FN) |
| 1 | 0.333 | 1.000 | 0.500 | 1 | 2 | 0 |
| 2 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| 3 | 0.500 | 0.500 | 0.500 | 1 | 1 | 1 |
| 4 | 0.667 | 1.000 | 0.800 | 2 | 1 | 0 |
| 5 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| 6 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| 7 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| 8 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| 9 | 0.333 | 1.000 | 0.500 | 2 | 4 | 0 |
| 10 | 0.200 | 1.000 | 0.333 | 1 | 4 | 0 |
| 11 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| 12 | 0.500 | 1.000 | 0.667 | 1 | 1 | 0 |
| 13 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| 14 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| 15 | 0.500 | 1.000 | 0.667 | 1 | 1 | 0 |
| 16 | 0.500 | 1.000 | 0.667 | 1 | 1 | 0 |
| 17 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| 18 | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| 19 | 0.500 | 1.000 | 0.667 | 1 | 1 | 0 |
| 20 | 0.500 | 1.000 | 0.667 | 1 | 1 | 0 |
| Summary | Summary | Summary | Summary | Summary | Summary | Summary |
| Micro | 0.595 | 0.962 | 0.735 | 25 | 17 | 1 |
| Macro | 0.727 | 0.975 | 0.798 | - | - | - |