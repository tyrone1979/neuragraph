from flask import Flask,render_template
from ui.dataset_api import dataset_bp
from ui.graph_api import graph_bp
from ui.agent_api import agent_bp
from ui.stream_api import sse_bp
from ui.testset_api import testset_bp
from ui.tool_api import tool_bp
from ui.llm_api import llm_bp
from ui.experiment_api import exp_bp
from ui.components.runner_selector import common_bp
from plugin.plugin_loader import get_plugin, _aclose_plugins
import sys
import asyncio
import atexit

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def create_app():
    app = Flask(__name__)

    def close_sync_plugins(exc=None):
        """关闭所有同步资源"""
        try:
            cm = get_plugin("postgres_sync_cm")
            if cm:
                cm.__exit__(None, None, None)

        except Exception as e:
            print(__name__).warning("sync close failed: %s", e)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop:
            loop.create_task(_aclose_plugins())
        else:
            # 循环已关闭（少见），新建一个跑最后一次
            asyncio.run(_aclose_plugins())



    atexit.register(close_sync_plugins)
    # 🔹 4. 注册 blueprint
    app.register_blueprint(sse_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(graph_bp)
    app.register_blueprint(dataset_bp)
    app.register_blueprint(testset_bp)
    app.register_blueprint(tool_bp)
    app.register_blueprint(llm_bp)
    app.register_blueprint(exp_bp)
    app.register_blueprint(common_bp)

    # 🔹 5. 路由
    @app.route("/", methods=["GET"])
    def index():
        from service.meta.loader import MetaLoader
        from service.entity.test import TestLoader

        stats = {
            "agents_count": MetaLoader.count("agents"),
            "graph_count": MetaLoader.count("graphs"),
            "tool_count": MetaLoader.count("tools"),
            "llms_count": MetaLoader.count("llms"),
            "exp_count": MetaLoader.count("exps"),
            "data_count": TestLoader.count()
        }
        return render_template("index.html", stats=stats)

    return app
if __name__ == '__main__':
    app=create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)
