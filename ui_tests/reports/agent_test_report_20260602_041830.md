# Agent Test Report

- Generated: 2026-06-02T04:18:30.113385+00:00
- Mock LLM: False (live = real deepseek / gpt-oss_120b only)
- Total: 1 | Passed: 0 | Failed: 1 | Skipped: 0

| Agent | Type | Status | ms | Message | Output preview |
| --- | --- | --- | ---: | --- | --- |
| `ontology_synonym_extract` | LLM | **FAIL** | 24640 | invoke exception: cannot access local variable 'parse_as' where it is not associated with a value | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\suites\agent_invoke_mock_llm_suite.py", line 413, in run_single_agent
    result = _invoke_loaded(runner)
             ^^^^^^^^^^^^^^^^^^^^^^
  File "D:\projects\agentic_llmre\ui_tests\suites\agent_invoke_mock_llm_suite.py", line 392, in _invoke_loaded
    return runner.invoke(inputs, config=config)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
UnboundLocalError: cannot access local variable 'parse_as' where it is not associated with a value
 |
