# Quick User Manual

[README](../README.md) · [CODE_WIKI](CODE_WIKI.md) · [EXPERIMENT_GUIDE](EXPERIMENT_GUIDE.md)

## 1. First-Time Setup

1. Start the server:
```bash
.\start.bat
```
2. Open `http://127.0.0.1:5001`.

- <img src="images/homepage.png" width="300">

## 2. Configure LLMs

- On the home page, click **Create New LLM**.
- <img src="images/btn_create_LLM.png" width="100">
- Complete the LLM form and click **Create**.
- <img src="images/page_new_llm.png" width="300">
- Click **Test Connection** to verify endpoint settings.
- <img src="images/btn_test_connection.png" width="300">

## 3. Create and Test Agents

- Open **Agents** from the top menu.
- <img src="images/menu.png" width="300">
- Click **Create New Agent**.
- <img src="images/page_agent_list.png" width="300">

Agent types:

- **LLM**: prompt template + model + optional tools
  - <img src="images/page_agent_left.png" width="300">
- **PGM**: local Python process, reads from `state`, writes to `__result__`
  - <img src="images/page_agent_pgm_left.png" width="300">
- **SUB** (legacy): subgraph loop controller
  - <img src="images/page_agent_sub_left.png" width="300">

Agent testing panel:

- <img src="images/page_agent_test_right.png" width="300">
- Select a test input from `/tests/<agent_id>/` or enter JSON manually.
- Run the test and inspect streamed output.
- <img src="images/page_agent_test_output_right.png" width="300">

## 4. Create and Test Workflows

- Open **Workflows**.
- <img src="images/page_graph_list.png" width="300">
- Click **Create New Workflow**.
- Edit ID, name, description, nodes, and edges.
- <img src="images/page_graph_edit_panel.png" width="300">
- View the rendered graph in the canvas.
- <img src="images/page_graph_graph_panel.png" width="400">

Additional workflow operations:

- Subgraph visualization
  - <img src="images/page_graph_subgraph.png" width="200">
- Agent detail panel
  - <img src="images/page_graph_right_panel.png" width="300">
- Agent test modal in graph editor
  - <img src="images/page_graph_agent_test.png" width="300">
- Full workflow test modal
  - <img src="images/page_graph_graph_test.png" width="300">

## 5. Run Experiments

- Open **Experiment** from top navigation.
- <img src="images/page_exp_list.png" width="300">
- Create a new experiment and select runner + dataset.
- <img src="images/page_exp_new.png" width="300">
- Start execution and monitor progress.
- <img src="images/page_exp_running.png" width="300">
- After completion, inspect replay and stored states.
- <img src="images/page_exp_completed.png" width="300">
- Open the **Report** tab for generated summary output.
- <img src="images/page_exp_report.png" width="300">

## 6. Manage Datasets

- Open **Dataset**.
- <img src="images/page_dataset_list.png" width="300">
- Upload and bind dataset files to a workflow or agent id.

## 7. Manage Tools

- Open **Tools**.
- <img src="images/page_tools_list.png" width="300">
- Create or edit local Python function tools used by LLM agents.
- <img src="images/page_tools_edit.png" width="300">

## 8. Practical Tips

- Keep test inputs aligned with workflow bindings.
- Use experiment mode for batch runs and metric tracking.
- Keep prompts deterministic when comparing model outputs.
- Prefer loop flow nodes for new iterative workflows.