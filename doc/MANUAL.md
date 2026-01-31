# Quick User Manual

## 1. First-time Setup
1. Start server 
```bash
python run.sh
```
2. Open http://127.0.0.1:5001
- <img src="images/homepage.png" width="300">

## 2. Operations
### 1. Setup a LLM
- Jump to the homepage and click "Create New LLM".
- <img src="images/btn_create_LLM.png" width="100">
- Fill in the LLM config details and hit "Create".
- <img src="images/page_new_llm.png" width="300">
- Test it out by clicking "Test Connection".
- <img src="images/btn_test_connection.png" width="300">

### 2. Create an Agent
- Head to "Agents" in the top nav or "Manage Agents" from the homepage.
- <img src="images/menu.png" width="300">
- On the Agents list page, click "Create New Agent".
- <img src="images/page_agent_list.png" width="300">
- Fill out the Agent form on the left (ID, name, description, type, prompt template, tools, LLM model).
  - The unique **agent id** follows python identifier rules.
  - Agent **name** is displayed in Agents list and workflow graph panel.
    - Type: Three Agent types: LLM, Program (PGM), or Loop controller (SUB).
      - **LLM** is an agent invoke LLM with **Prompt Template** and Tools configuration
      - <img src="images/page_agent_left.png" width="300">
      - **PGM** is an agent execute local python code. In the code area. 
      You can use <code>state</code> dict to read/write data. 
      Use <code>get_plugin()</code> to get plugin objects. 
      Set return values to <code>__result__ = ...</code>
      - <img src="images/page_agent_pgm_left.png" width="300">
      - **SUB** is an subgraph(contains multiple agents) with loop controller function. For some reason. The ID of a SUB must be a <code>sub_</code> prefix.
      It cannot be executed lonely. Index for loop must be provided.
      - <img src="images/page_agent_sub_left.png" width="300">
      If input is sentences, index is set to sentence. The SUB is executed as below demo.
      ```python
      for sentence in state['sentences']:
         out=agent.invoke({ 'input': sentence})
      ```
      - **Inputs** are the objects read from <code>state</code> by Agents.
      e.g. If a LLM prompt template is set as below, inputs must be set as <code>title,abstract<code>.
      ```
      split the below text into sentence.
      {title}
      {abstract}
      ```
      If the inputs of two agents in a SUB are <code>text</code> and <code>labels</code>,
      the inputs of SUB must be set as <code>text,labels</code>.
    - **Outputs** is the output of an agent. Currently, limit it as one variable. You can set it as any built-in type.
  
- Test Agent at the right of page. 
  - <img src="images/page_agent_test_right.png" width="300">
  - Selected one from Test dataset dropdown. The test data is from test file located at /tests/<agent_id>/
  - Or you can input test data manually.
  - [Refresh] button can reload test files.
  - [Save] for new test data.
  - [Run Test] to launch test and output from Agent will be streaming at Output area.
  - <img src="images/page_agent_test_output_right.png" width="300">
  
### 3. Create a Workflow(Graph)
- Click "Workflows" in Top Navigator or "View Workflows" at homepage.
- <img src="images/page_graph_list.png" width="300">
- Click "Create New Workflow" in Workflow list page
  - In [Edit Panel], Input Workflow ID, Name, Description
  - Click [Add Node] and input agent name in Nodes for searching. The candidates will list down.
  - For performance reason, **Agents with tools will not show up**.
  - Click [Add Edge], and start from START node and end with END node.
  - **ATTENTION**, There is no input/output validation. 
  - The output of previous node maps the input of next node with same name.
  - <img src="images/page_graph_edit_panel.png" width="300">
  - After [Edit Panel] editing, Graph Panel will show the workflow graph.
  - <img src="images/page_graph_graph_panel.png" width="400">
  - Right click on the panel, Download SVG of the graph.
- For the workflow with iteration(Loop) subgraph, you must create a workflow with <code>sub_<code> prefix id in advance. The id must be the same with SUB agent id.
- <img src="images/page_graph_subgraph.png" width="200">
- Double click on the node, The info of the agent will show on right side panel.
- <img src="images/page_graph_right_panel.png" width="300">
- Click [Test], show Test Panel. Select a test data file, click [Test] button, the agent is launched and response is printed streamingly on [Execution Results]
- <img src="images/page_graph_agent_test.png" width="300">
- Click [Test Workflow] on the right top button group for workflow test. Select a test data file, click [Test] button, the workflow is launched and response is printed streamingly on [Execution Results] 
- <img src="images/page_graph_graph_test.png" width="300">

### 3. Create an Experiment
- Click "Experiment" in Top Navigator or "View Experiments" at homepage.
- <img src="images/page_exp_list.png" width="300">
- Click [New Experiment] in the experiment list page.
- Input Workflow or Graph id in Runner search input and select one candidate, Test set(Dataset) files show the right select, and data preview will show on the table.
- <img src="images/page_exp_new.png" width="300">
- Click [Start Experiment] to launch the workflow/agent. The workflow will feed data one by one to workflow/agent. The progress/status is keeping updating.
- <img src="images/page_exp_running.png" width="300">
- 500 records pressure test was passed.
- **ATTENTION** When the experiment was launched, **DO NOT** close the browser until it completed.
- After the progress is updated to 100%, The page will refresh, and in actions column, [Replay] button will show.
- Click [Replay] button of any record, the experiment raw result will show on the modal.
- The result will be persistently stored in /result/<exp_id>/states.json.
- <img src="images/page_exp_completed.png" width="300">
- Click [Report] tab on the top, a report will be made based on the total results by built-in LLM agent.
- <img src="images/page_exp_report.png" width="300">

### 4. Upload Datasets
- Click "Dataset" in Top Navigator or "View Dataset" at homepage.
- <img src="images/page_dataset_list.png" width="300">
- Input agent/workflow id in the input for searching and upload a data file. The dataset bind with an agent/workflow.

### 5. Tools
- Click "Tools" in Top Navigator or "Browse Tools" at homepage.
- <img src="images/page_tools_list.png" width="300">
- "Tool" is defined as a local python function to be called by LLM. **No restful api calling function** by now.
- Click [New Tool] or [Edit] of existed tools, you can edit and run it.
  - <img src="images/page_tools_edit.png" width="300">
  - Call a tool in LLM
  - In Agent Edit page, select one tool, than edit the prompt template as below an example.
  ```markdown
      You are performing biomedical hypernym identification.
      Input data:
      Heads: {heads}
      Tails: {tails}
  
      Merge the provided heads and tails into a unified entity list.
      **Call the tool `merge_heads_tails_to_entities`** with the exact heads and tails provided above.
  
      Once you receive the merged entities string from the tool (format: text,type,mesh per line),
      analyze it according to the following strict rules:
  
      Rules:
      1. Entities of different types (e.g., Disease vs Chemical) have NO hierarchical relationship.
      2. For each entity, find its immediate hypernym ONLY within entities of the SAME type.
      3. A hypernym must share the exact same MeSH code prefix or be explicitly broader within the same type bucket.
      4. If no hypernym exists in the same type, output nothing for that entity.
      5. Never invent relationships across types.
  
      Final output format (strict, no extra text):
      entity_text→hypernym_text
      One per line, only for entities that have a hypernym.
      If none, output nothing."
  ```
## 3. Advanced Tips

- Persistence: Default in-memory; uncomment Postgres in plugins.py for state saving.
- Custom Prompts: In tools/agents, tweak system/human prompts for better BioNLP accuracy.
- Metrics: NER/RE evals use precision/recall/F1; 