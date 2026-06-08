Copy this folder to sandbox/<your_id>/ and register in meta/plugins_sandbox.json.

  .\sandbox\setup_venv.ps1 -Name <your_id>   (Windows)
  ./sandbox/setup_venv.sh <your_id>            (Linux / macOS)

Required files:
  sandbox/<your_id>/requirements.txt
  sandbox/<your_id>/plugins_impl.py   (Plugin subclasses)
  sandbox/<your_id>/plugin_server.py  (copy from flair/plugin_server.py, set SANDBOX_ID)
