**Author:** 磊 赵

NeuraGraph: A Visual Workflow Framework for Reproducible Biomedical Text Mining with LLM-Agents

Lei Zhao1, Changning Ren2, Xinning Liu2, Li Han2, Yingnan Fan2, Ling Kang1∗, Quan Guo1∗

1 Neusoft Research Institution, Dalian Neusoft University of Information, Dalian, 116023, China
2 Software Department, Dalian Neusoft University of Information, Dalian, 116023, China

*To whom correspondence should be addressed.
Email: kangling@neusoft.edu.cn, guoquan@neusoft.edu.cn, 

Abstract

Summary: Biomedical text mining increasingly demands hybrid pipelines integrating traditional NLP toolkits and LLM-based agents, yet orchestrating these heterogeneous components into reproducible workflows remains a major barrier for domain researchers without extensive coding expertise. NeuraGraph is a lightweight, open-source Python framework tailored for biomedical text mining, enabling minimal-code visual assembly of LLM-agent workflows with formal graph validation, recursive subgraph composition, and LLM-powered reporting. It features native parsers for biomedical benchmarks (CDR, ChemDisGene), one-line integration of local models (e.g., Flair), and out-of-the-box micro/macro metric logging—all with zero infrastructure dependencies. NeuraGraph streamlines experiment setup from hours to minutes while  for systematic hybrid extraction strategy comparison.

Availability and Implementation: NeuraGraph is implemented in Python 3.12+ and released under the MIT license, with all dependencies listed in a requirements.txt file for straightforward installation. Source code and documentation are available at https://github.com/tyrone1979/neuragraph. The software runs natively on Linux, macOS, and Windows with no mandatory external dependencies.

Contact:  zhaolei@neusoft.edu.cn

Supplementary information: Supplementary data are available at Bioinformatics online.

1 Introduction

Biomedical text mining is a cornerstone of translational bioinformatics(Cohen and Hunter 2013) enabl the extraction of actionable insights, e.g., chemical-disease relations, gene-phenotype associations from unstructured scientific literature (Lan et al. 2025, Xu and Sankar 2025). (Öztürk, Özgür, and Ozkirimli 2018)(Karimi et al. 2015)(Wei et al. 2020)

Modern mining pipelines increasingly adopt a hybrid paradigm that combines the reproducibility of traditional modular NLP tools such as Flair(Akbik et al. 2019) and SciSpacy(Neumann et al. 2019) with large language model based agents(Zhao, Kang, and Guo 2025). (Huang et al. 2025)This integration unlocks state-of-the-art performance for tasks such as named entity recognition (NER) and relation extraction (RE)(Jin, Choi, and Kim 2025, Lv et al. 2025), but introduces critical engineering challenges for biomedical researchers without extensive coding expertise. 

A central bottleneck in hybrid pipeline development is the orchestration of heterogeneous components into reproducible, evaluable workflows. General purpose workflow frameworks like LangChain and LangGraph(LangChain Team 2024) provide rich orchestration primitives but demand substantial coding effort, offer no built‑in support for biomedical benchmarks, and lack automated experiment logging and evaluation. On the other hand, low‑code platforms such as Dify(Dify 2025) and Flowise(Flowise 2023) are designed for production deployment, introduce infrastructure dependencies such as Docker, and do not facilitate fine‑grained, per‑instance error analysis required for methodical research. As a result, practitioners rely on ad-hoc scripting, hindering reproducibility and systematic comparison of extraction strategies.

To address these gaps, we present NeuraGraph, a lightweight, open-source workflow framework designed for reproducible biomedical text mining with hybrid LLM-agent pipelines. Building on a LangGraph core, NeuraGraph introduces three key innovations tailored to domain researchers: (1) formal input inference that statically validates workflow graphs to eliminate runtime data dependency errors; (2) recursive subgraph composition as a first-class primitive for hierarchical pipeline design and reuse; and (3) an LLM-powered reporting that converts raw logs into structured reports with quantitative metrics and qualitative failure pattern interpretation.

NeuraGraph is engineered for immediate usability: it ships with native parsers for established biomedical benchmarks such as BioCreative V CDR corpus (Li et al. 2016) and the ChemDisGene (Zhang et al. 2022) dataset, a browser-based visual editor with no code requirements, a secure plugin system for one-line integration of local biomedical NLP models, and automatic persistence of all experiment metadata as version-controllable JSON files. Unlike existing tools, NeuraGraph combines formal workflow validation, hierarchical subgraph reuse, and reporting in a zero-infrastructure, pure-Python environment—eliminating engineering overhead while guaranteeing full reproducibility. 

2 Implementation

NeuraGraph is implemented in Python 3.12+ and distributed under the MIT open-source license, with all core and optional dependencies explicitly listed in a requirements.txt file for straightforward installation. The framework requires no mandatory infrastructure dependencies (e.g., Docker, cloud services) and runs natively on consumer-grade hardware typical of biomedical research labs, including laptops with Intel i7 processors and 16 GB RAM. Resource-intensive LLM inference is decoupled from core execution and supported via lightweight API calls to lab-managed GPU servers running Ollama, ensuring compatibility with restricted network environments.

The framework embeds a suite of integrated functional modules optimized for end-to-end biomedical text mining pipeline development and validation, with key capabilities including:

The framework supports recursive subgraph composition, allowing any complete workflow to be encapsulated as a reusable node for hierarchical pipeline design—such as sentence-level named entity recognition (NER) within document-level relation extraction (RE). This modularity enables the creation of lab-specific libraries of portable biomedical text mining components, shared as JSON artifacts for immediate reuse across experiments.

Local biomedical NLP models (e.g., Flair) are integrated via a secure plugin system, with plugins isolated and cached after initial loading to prevent version conflicts. Pre-built plugins for common biomedical models are included, and a minimal template (≤50 lines of code) supports integration of custom local models for domain-specific tasks. All plugin interactions are managed within the core framework, requiring no additional configuration from end users.

Every experiment execution generates a self-contained JSON artifact that captures the complete experimental context: workflow configuration, input dataset, per-node execution traces, intermediate outputs, final predictions, and instance-level evaluation metrics. These artifacts enable one-command reproducibility, with identical results generated on any compatible installation of NeuraGraph. 

An LLM-powered reporting agent ingests these JSON logs to compute micro-averaged and macro-averaged precision, recall, and F1 scores, producing structured Markdown reports with performance summaries and natural-language interpretation of failure patterns. 

The reporting agent supports both local LLMs (e.g., Mistral 7B via Ollama) and cloud-based LLMs (e.g., GPT-4o), configurable via a simple settings panel to accommodate research labs with restricted internet access.

The end-to-end workflow of NeuraGraph, from data input to , is illustrated in Fig. 1. Detailed implementations of core features, including algorithm specifications and plugin development guidelines, are provided in the supplementary material.

Fig. 1. Workflow employed by the NeuraGraph framework for reproducible biomedical text mining with hybrid LLM-agent pipelines. (A) Raw biomedical text or benchmark datasets (CDR, ChemDisGene) are processed via native parsers, eliminating manual preprocessing. (B) Low-code workflow assembly is performed via a browser-based visual editor, with real-time validation of data dependencies and recursive subgraph support for hierarchical pipeline design. (C) Hybrid execution combines local framework operation (consumer-grade laptop) with remote LLM inference (GPU server via Ollama API). (D) Built-in metric calculation and per-instance error analysis avoid pseudoreplication bias via sample-level aggregation. (E) LLM-powered reporting generates structured evaluation reports with actionable refinement suggestions, closing the experimental loop.

3 Results

NeuraGraph was  on chemical/disease named entity recognition (NER) and chemical-induced disease (CID) relation extraction (RE) tasks using the BioCreative V CDR benchmark, 

 Implementation effort comparison for biomedical text mining pipelines: NeuraGraph vs. Custom Python code vs. Dify

Table Notes: 

NeuraGraph enabled minimal-code  assembly, with a NER pipeline and a hierarchical recursive subgraph RE pipeline  the visual editor local execution and JSON artifact generation were completed in 10 minutes for all 

By contrast, custom Python required  manual , environment configuration debugging, metric calculation. Dify required prompt engineering, API configuration, and Docker setup for local model integration.

The LLM-powered reporting agent automatically  artifacts to structured Markdown reports  quantitative metrics, error breakdowns

 and actionable refinement suggestions for  optimization.

End-to-end workflow examples for NER and CID  tasks,  with per-instance performance metrics structured output , are  in the supplementary material.

 Conclusion

NeuraGraph establishes a lightweight, minimal-code workflow framework that streamlines the development and evaluation of hybrid LLM-agent pipelines for reproducible biomedical text mining. By integrating real-time workflow validation, recursive subgraph composition, native biomedical benchmark support, and LLM-powered reporting into a pure-Python, zero-infrastructure environment, the framework drastically reduces implementation effort—cutting pipeline setup time from hours to minutes—while maintaining competitive performance on the BioCreative V CDR benchmark. Its enforcement of key research best practices, such as sample-level metric aggregation to avoid pseudoreplication bias and one-command reproducibility via persistent JSON artifacts, ensures scientific rigor. As an open-source tool tailored for standard research lab hardware, NeuraGraph lowers the technical barrier for domain researchers to systematically design, execute, and refine hybrid extraction strategies, facilitating faster empirical comparison and accelerating insights from unstructured biomedical literature.

Acknowledgements

This work was supported by Key Projects of the Fundamental Research Program for Higher Education Institutions in Liaoning Province [LJ232513631003, LJ212513631003].

References

Akbik A, Bergmann T, Blythe D et al. FLAIR: An easy-to-use framework for state-of-the-art NLP. Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics (Demonstrations) 2019:54–9.

Cohen KB, Hunter LE. Chapter 16: Text Mining for Translational Bioinformatics. PLOS Computational Biology 2013;9(4):e1003044. https://doi.org/10.1371/journal.pcbi.1003044.

Dify. Dify: Open-source LLM app development platform. 2025. https://dify.ai/ (22 Jan. 2025, date last accessed).

Flowise. Flowise: Open-source low-code tool for building customized LLM flows. 2023. https://flowiseai.com/ (22 Jan. 2025, date last accessed).

Huang Z, Chen X, Wang Y et al. A survey on biomedical automatic text summarization with large language models. Information Processing & Management 2025;62(5):104216. https://doi.org/10.1016/j.ipm.2025.104216.

Jin M, Choi SM, Kim GW. COMCARE: A Collaborative Ensemble Framework for Context-Aware Medical Named Entity Recognition and Relation Extraction. Electronics 2025;14(2):328. https://doi.org/10.3390/electronics14020328.

Karimi S, Wang C, Metke-Jimenez A et al. Text and Data Mining Techniques in Adverse Drug Reaction Detection. ACM Comput Surv (New York, NY, USA) 2015;47(4). https://doi.org/10.1145/2719920.

Lan W, Tang Z, Liu M et al. The large language models on biomedical data analysis: a survey. IEEE Journal of Biomedical and Health Informatics 2025.

LangChain Team. LangGraph: Build resilient language agents as graphs. 2024. https://github.com/langchain-ai/langgraph (22 Jan. 2026, date last accessed).

Li J, Sun Y, Johnson RJ et al. BioCreative V CDR task corpus: a resource for chemical disease relation extraction. Database 2016;2016:baw068. https://doi.org/10.1093/database/baw068.

Lv T, Luo L, Li J et al. A Unified Biomedical Named Entity Recognition Framework with Large Language Models. 2025. https://arxiv.org/abs/2510.08902.

Neumann M, King D, Beltagy I et al. ScispaCy: fast and robust models for biomedical natural language processing. arXiv Preprint arXiv:190207669 2019.

Öztürk H, Özgür A, Ozkirimli E. DeepDTA: deep drug–target binding affinity prediction. Bioinformatics 2018;34(17):i821–9. https://doi.org/10.1093/bioinformatics/bty593.

Wei Q, Ji Z, Li Z et al. A study of deep learning approaches for medication and adverse drug event extraction from clinical text. Journal of the American Medical Informatics Association 2020;27(1):13–21. https://doi.org/10.1093/jamia/ocz063.

Xu X, Sankar R. Large language model agents for biomedicine: a comprehensive review of methods, evaluations, challenges, and future directions. Information 2025;16(10):894.

Zhang D, Mohan S, Torkar M et al. A Distant Supervision Corpus for Extracting Biomedical Relationships Between Chemicals, Diseases and Genes, arXiv:2204.06584. Preprint, arXiv, 13 Apr. 2022. https://doi.org/10.48550/arXiv.2204.06584.

Zhao L, Kang L, Guo Q. Zero-Shot Document-Level Biomedical Relation Extraction via Scenario-based Prompt Design in Two-Stage with LLM. 2025. https://arxiv.org/abs/2505.01077.


### Table 1

|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |


### Table 2

|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |


### Table 3

| Task | Implementation Approach (unit: code line) | Implementation Approach (unit: code line) | Implementation Approach (unit: code line) |
| Task | NeuraGraph | Custom Python code | Dify |
| Chemical/Disease NER | 18 | 302 | 101 |
| Chemical-induced disease RE | 16 | 307 | 149 |