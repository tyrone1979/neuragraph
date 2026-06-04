# Agent Test Report

- Generated: 2026-06-02T00:36:16.953295+00:00
- Mock LLM: True
- Total: 42 | Passed: 0 | Failed: 42 | Skipped: 0

| Agent | Type | Status | ms | Message | Output preview |
| --- | --- | --- | ---: | --- | --- |
| `agent_refiner` | LLM | **FAIL** | 2962 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `cid_pair_generate` | PGM | **FAIL** | 46 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `dataset_cid_tuning_build` | PGM | **FAIL** | 50 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `eval_flair` | PGM | **FAIL** | 47 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `eval_llm` | PGM | **FAIL** | 45 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `eval_metrics` | PGM | **FAIL** | 46 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `eval_metrics_relation` | PGM | **FAIL** | 46 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `eval_metrics_segment` | PGM | **FAIL** | 47 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `eval_pair_generate` | PGM | **FAIL** | 43 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `kg_rdf_export` | PGM | **FAIL** | 47 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `kg_triple_extract_llm` | LLM | **FAIL** | 306 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `kg_triple_merge` | PGM | **FAIL** | 47 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `kg_triple_persist` | PGM | **FAIL** | 56 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `merge_metrics` | PGM | **FAIL** | 43 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `ner_comparison_report` | LLM | **FAIL** | 65 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `ner_flair_aggregate` | PGM | **FAIL** | 38 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `ner_flair_doc` | PGM | **FAIL** | 49 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `ner_flair_sent` | PGM | **FAIL** | 44 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `ner_from_tree_llm` | LLM | **FAIL** | 58 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `ner_llm` | LLM | **FAIL** | 44 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `ontology_entity_link` | LLM | **FAIL** | 69 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `ontology_hypernym_filter` | LLM | **FAIL** | 75 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `ontology_hypernym_identify` | LLM | **FAIL** | 222 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `ontology_mesh_lookup` | PGM | **FAIL** | 69 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `ontology_synonym_extract` | LLM | **FAIL** | 269 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `ontology_synonym_resolve` | LLM | **FAIL** | 62 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `relation_dti_analyze` | LLM | **FAIL** | 68 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `relation_extract_llm` | LLM | **FAIL** | 59 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `relation_extract_pubtator` | PGM | **FAIL** | 59 | invoke exception: <module 'plugin.plugins' from 'D:\\projects\\agentic_llmre\\plugin\\plugins.py'> does not have the attribute 'get_plugin' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 256, in run_single_agent
    with _pubtator_plugin_mock():
  File "D:\anaconda3\Lib\contextlib.py", line 137, in __enter__
    return next(self.gen)
           ^^^^^^^^^^^^^^
AttributeError: <module 'plugin.plugins' from 'D:\\projects\\agentic_llmre\\plugin\\plugins.py'> does not have the attribute 'get_plugin'
 |
| `relation_from_tree_llm` | LLM | **FAIL** | 375 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `relation_result_to_id_pair` | PGM | **FAIL** | 41 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `relation_verify_llm` | LLM | **FAIL** | 50 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `relation_verify_to_pair` | PGM | **FAIL** | 40 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `report_comparator` | LLM | **FAIL** | 93 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `report_experiment` | LLM | **FAIL** | 61 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `report_experiment_tool` | LLM | **FAIL** | 101 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `report_format_json` | PGM | **FAIL** | 45 | invoke exception: AgentEntity.invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AgentEntity.invoke() got an unexpected keyword argument 'config'
 |
| `syntax_dep_parse` | LLM | **FAIL** | 189 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `text_coreference` | LLM | **FAIL** | 157 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `text_sentence_split` | LLM | **FAIL** | 31 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `text_summarize` | LLM | **FAIL** | 32 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
| `text_word_segment` | LLM | **FAIL** | 161 | invoke exception: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config' | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\agent_test_suite.py", line 259, in run_single_agent
    result = runner.invoke(inputs, config=config)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: _llm_mock_context.<locals>.patched_invoke() got an unexpected keyword argument 'config'
 |
