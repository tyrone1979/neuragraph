# Agent Test Report

- Generated: 2026-06-02T04:15:21.546801+00:00
- Mock LLM: False (live = real deepseek / gpt-oss_120b only)
- Total: 1 | Passed: 0 | Failed: 1 | Skipped: 0

| Agent | Type | Status | ms | Message | Output preview |
| --- | --- | --- | ---: | --- | --- |
| `agent_refiner` | LLM | **FAIL** | 4294 | invoke exception: Single '}' encountered in format string | Traceback (most recent call last):
  File "D:\projects\agentic_llmre\ui_tests\suites\agent_invoke_mock_llm_suite.py", line 403, in run_single_agent
    runner = AgentLoader.load(agent_id)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\projects\agentic_llmre\service\entity\agent.py", line 600, in load
    return AgentEntity(meta, checkpointer=checkpointer)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: Single '}' encountered in format string
 |
