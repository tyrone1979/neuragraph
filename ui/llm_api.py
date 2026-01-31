# llm_api.py
from flask import Blueprint, render_template, request, jsonify, abort
import requests
from typing import Dict, Any, List
from service.meta.loader import MetaLoader

llm_bp = Blueprint('llm', __name__, url_prefix='/llms')

def _test_custom(config: Dict[str, Any]) -> Dict[str, Any]:
    """测试自定义 LLM 接口"""
    base_url = config.get("base_url", "")
    api_key = config.get("api_key", "")

    if not base_url:
        return {"success": False, "error": "Base URL is required"}

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = {
        "messages": [
            {
                "role": "system",
                "content": ""
            },
            {
                "role": "user",
                "content": "hello"
            }
        ],
        "model": config.get("model", "")
    }

    url = base_url.rstrip("/") + "/chat/completions"
    response = requests.post(url, headers=headers, json=data, timeout=10)
    if response.status_code == 200:
        return {
                    "success": True,
                    "message": f"Custom LLM connection successful",
                    "status_code": response.status_code,
                }
    else:
        return {"success": False, "error": f"Custom LLM error: {response.text[:200]}"}


def _test_openai(config: Dict[str, Any]) -> Dict[str, Any]:
    """测试 OpenAI 兼容接口"""
    base_url = config.get("base_url", "https://api.openai.com/v1")
    api_key = config.get("api_key", "")
    model = config.get("model", "gpt-3.5-turbo")

    if not api_key:
        return {"success": False, "error": "API key is required"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 如果 base_url 是 OpenAI，使用 models 端点
    if "openai.com" in base_url:
        url = f"{base_url}/models"
    else:
        url = f"{base_url}/models"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        models = response.json().get("data", [])
        model_names = [m["id"] for m in models]

        return {
            "success": True,
            "message": f"Connection successful. Available models: {', '.join(model_names[:5])}...",
            "available_models": model_names,
            "status_code": response.status_code
        }
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Connection timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Connection failed"}
    except Exception as e:
        return {"success": False, "error": f"API error: {str(e)}"}



# 同时需要更新测试函数中的对应部分
def _test_azure(config: Dict[str, Any]) -> Dict[str, Any]:
    """测试 Azure OpenAI 接口（更完善的版本）"""
    endpoint = config.get("endpoint", "")
    api_key = config.get("api_key", "")
    deployment = config.get("deployment", config.get("model", ""))
    api_version = config.get("api_version", "2023-05-15")

    if not endpoint:
        return {"success": False, "error": "Endpoint is required"}
    if not api_key:
        return {"success": False, "error": "API key is required"}

    # 尝试获取模型列表
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    if "openai.azure.com" in endpoint:
        # 标准 Azure OpenAI
        if "/openai/deployments" in endpoint:
            # 已经是 deployments 端点
            base_url = endpoint.split("/openai/deployments")[0]
        else:
            base_url = endpoint.rstrip("/")

        url = f"{base_url}/openai/deployments?api-version={api_version}"
    else:
        # 自定义 Azure 端点
        url = f"{endpoint.rstrip('/')}/openai/deployments?api-version={api_version}"

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            deployments = response.json().get("value", [])
            deployment_names = [d["id"] for d in deployments]

            # 如果有指定的 deployment，检查是否存在
            if deployment:
                if deployment in deployment_names:
                    return {
                        "success": True,
                        "message": f"Azure OpenAI connection successful. Deployment '{deployment}' exists.",
                        "available_deployments": deployment_names,
                        "status_code": response.status_code
                    }
                else:
                    return {
                        "success": True,
                        "message": f"Azure OpenAI connection successful, but deployment '{deployment}' not found.",
                        "available_deployments": deployment_names,
                        "status_code": response.status_code,
                        "warning": f"Deployment '{deployment}' not found in available deployments"
                    }
            else:
                return {
                    "success": True,
                    "message": f"Azure OpenAI connection successful. Found {len(deployment_names)} deployments.",
                    "available_deployments": deployment_names,
                    "status_code": response.status_code
                }
        else:
            # 如果获取部署列表失败，尝试直接调用聊天接口
            if deployment:
                test_result = _test_azure_with_chat(config)
                if test_result["success"]:
                    return test_result
                else:
                    return {
                        "success": False,
                        "error": f"Failed to get deployments and chat test also failed: {test_result.get('error', 'Unknown error')}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get deployments: {response.status_code}"
                }

    except Exception as e:
        return {"success": False, "error": f"Azure API error: {str(e)}"}


def _test_azure_with_chat(config: Dict[str, Any]) -> Dict[str, Any]:
    """通过聊天接口测试 Azure OpenAI"""
    endpoint = config.get("endpoint", "")
    api_key = config.get("api_key", "")
    deployment = config.get("deployment", config.get("model", ""))
    api_version = config.get("api_version", "2023-05-15")

    if not deployment:
        return {"success": False, "error": "Deployment name is required for chat test"}

    if "openai.azure.com" in endpoint:
        base_url = endpoint.rstrip("/")
        if "/openai/deployments" not in base_url:
            url = f"{base_url}/openai/deployments/{deployment}/chat/completions"
        else:
            url = f"{endpoint.rstrip('/')}/chat/completions"
    else:
        url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions"

    url = f"{url}?api-version={api_version}"

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    data = {
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 5
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.status_code == 200:
            return {
                "success": True,
                "message": "Azure OpenAI chat API is working",
                "status_code": response.status_code
            }
        else:
            error_detail = ""
            try:
                error_response = response.json()
                error_detail = error_response.get("error", {}).get("message", str(response.status_code))
            except:
                error_detail = str(response.status_code)
            return {
                "success": False,
                "error": f"Chat API failed: {error_detail}",
                "status_code": response.status_code
            }

    except Exception as e:
        return {"success": False, "error": f"Chat test error: {str(e)}"}


# 更新 _test_anthropic 函数
def _test_anthropic(config: Dict[str, Any]) -> Dict[str, Any]:
    """测试 Anthropic Claude 接口（更完善的版本）"""
    api_key = config.get("api_key", "")

    if not api_key:
        return {"success": False, "error": "API key is required"}

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    # 尝试获取模型列表
    try:
        models_url = "https://api.anthropic.com/v1/models"
        response = requests.get(models_url, headers=headers, timeout=10)

        if response.status_code == 200:
            models = response.json().get("data", [])
            model_names = [m["id"] for m in models]

            # 检查指定模型是否存在
            specified_model = config.get("model")
            if specified_model:
                if specified_model in model_names:
                    return {
                        "success": True,
                        "message": f"Anthropic Claude connection successful. Model '{specified_model}' is available.",
                        "available_models": model_names,
                        "status_code": response.status_code
                    }
                else:
                    return {
                        "success": True,
                        "message": f"Anthropic Claude connection successful, but model '{specified_model}' not found.",
                        "available_models": model_names,
                        "status_code": response.status_code,
                        "warning": f"Model '{specified_model}' not found in available models"
                    }
            else:
                return {
                    "success": True,
                    "message": f"Anthropic Claude connection successful. Found {len(model_names)} models.",
                    "available_models": model_names,
                    "status_code": response.status_code
                }
        else:
            # 如果获取模型列表失败，尝试直接调用消息接口
            test_result = _test_anthropic_with_messages(config)
            if test_result["success"]:
                return test_result
            else:
                return {
                    "success": False,
                    "error": f"Failed to get models and message test also failed: {test_result.get('error', 'Unknown error')}"
                }

    except Exception as e:
        return {"success": False, "error": f"Anthropic API error: {str(e)}"}


def _test_anthropic_with_messages(config: Dict[str, Any]) -> Dict[str, Any]:
    """通过消息接口测试 Anthropic Claude"""
    api_key = config.get("api_key", "")
    model = config.get("model", "claude-3-haiku-20240307")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    url = "https://api.anthropic.com/v1/messages"

    data = {
        "model": model,
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 5
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.status_code == 200:
            return {
                "success": True,
                "message": "Anthropic Claude messages API is working",
                "status_code": response.status_code
            }
        else:
            error_detail = ""
            try:
                error_response = response.json()
                error_detail = error_response.get("error", {}).get("message", str(response.status_code))
            except:
                error_detail = str(response.status_code)
            return {
                "success": False,
                "error": f"Messages API failed: {error_detail}",
                "status_code": response.status_code
            }

    except Exception as e:
        return {"success": False, "error": f"Message test error: {str(e)}"}



# 其他生成函数的实现类似...
def validate_llm_config(config: Dict[str, Any]) -> List[str]:
    """验证 LLM 配置，返回错误列表"""
    errors = []

    # 检查必要字段
    required_fields = ["type"]
    for field in required_fields:
        if not config.get(field):
            errors.append(f"Missing required field: {field}")

    # 类型特定验证
    llm_type = config.get("type", "").lower()

    # 检查必要字段
    if llm_type == "ollama":
        required_fields = ["model", "type"]
        # Ollama 不需要 API key
    else:
        required_fields = ["model", "type", "api_key"]
    for field in required_fields:
        if not config.get(field):
            errors.append(f"Missing required field: {field}")
    # 类型特定验证
    if llm_type == "ollama":
        if not config.get("base_url"):
            config["base_url"] = "http://localhost:11434"
        if not config.get("model"):
            config["model"] = "llama2"

        # 验证 URL 格式
        base_url = config.get("base_url", "")
        if base_url and not (base_url.startswith("http://") or base_url.startswith("https://")):
            errors.append("Ollama base URL must start with http:// or https://")

    if llm_type == "openai":
        if not config.get("base_url"):
            config["base_url"] = "https://api.openai.com/v1"  # 设置默认值
        if not config.get("model"):
            config["model"] = "gpt-3.5-turbo"  # 设置默认值

    elif llm_type == "azure":
        if not config.get("endpoint"):
            errors.append("Azure endpoint is required")
        if not config.get("deployment") and not config.get("model"):
            errors.append("Azure deployment/model name is required")

    elif llm_type == "anthropic":
        if not config.get("model"):
            config["model"] = "claude-3-haiku-20240307"

    elif llm_type == "custom":
        if not config.get("base_url"):
            errors.append("Custom base URL is required")

    # 验证数值范围
    if config.get("max_tokens"):
        try:
            max_tokens = int(config["max_tokens"])
            if max_tokens <= 0 or max_tokens > 32000:
                errors.append("max_tokens must be between 1 and 32000")
        except ValueError:
            errors.append("max_tokens must be a valid number")

    if config.get("temperature"):
        try:
            temperature = float(config["temperature"])
            if temperature < 0 or temperature > 2:
                errors.append("temperature must be between 0 and 2")
        except ValueError:
            errors.append("temperature must be a valid number")

    return errors




def _test_ollama(config: Dict[str, Any]) -> Dict[str, Any]:
    """测试 Ollama 连接"""
    base_url = config.get("base_url", "http://localhost:11434")
    model = config.get("model", "llama2")

    # Ollama 不需要 API key，但如果提供了也接受
    api_key = config.get("api_key", "")

    # 构建请求头
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # 尝试多个端点
    test_endpoints = ["/api/tags", "/api/version", "/"]

    for endpoint in test_endpoints:
        try:
            url = base_url.rstrip("/") + endpoint
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                # 如果是 /api/tags 端点，解析可用模型
                if endpoint == "/api/tags":
                    try:
                        models_data = response.json()
                        available_models = [model_info["name"] for model_info in models_data.get("models", [])]

                        # 检查指定模型是否存在
                        if model:
                            model_exists = any(m.startswith(model) for m in available_models)
                            if model_exists:
                                return {
                                    "success": True,
                                    "message": f"Ollama connection successful. Model '{model}' is available.",
                                    "available_models": available_models,
                                    "endpoint": endpoint,
                                    "status_code": response.status_code
                                }
                            else:
                                return {
                                    "success": True,
                                    "message": f"Ollama connection successful, but model '{model}' not found.",
                                    "available_models": available_models,
                                    "endpoint": endpoint,
                                    "status_code": response.status_code,
                                    "warning": f"Model '{model}' not found in available models"
                                }
                        else:
                            return {
                                "success": True,
                                "message": f"Ollama connection successful. Found {len(available_models)} models.",
                                "available_models": available_models,
                                "endpoint": endpoint,
                                "status_code": response.status_code
                            }
                    except:
                        # 如果解析失败，至少连接成功
                        return {
                            "success": True,
                            "message": f"Ollama connection successful (endpoint: {endpoint})",
                            "status_code": response.status_code
                        }
                else:
                    return {
                        "success": True,
                        "message": f"Ollama connection successful (endpoint: {endpoint})",
                        "status_code": response.status_code
                    }
        except requests.exceptions.Timeout:
            return {"success": False, "error": f"Connection timeout to {endpoint}"}
        except requests.exceptions.ConnectionError:
            continue  # 尝试下一个端点
        except Exception as e:
            continue  # 尝试下一个端点

    # 如果所有端点都失败，尝试 POST 请求
    try:
        url = base_url.rstrip("/") + "/api/generate"
        data = {
            "model": model,
            "prompt": "Hello",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 5
            }
        }

        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.status_code == 200:
            return {
                "success": True,
                "message": "Ollama generate API is working",
                "status_code": response.status_code
            }
        else:
            error_detail = ""
            try:
                error_response = response.json()
                error_detail = error_response.get("error", str(response.status_code))
            except:
                error_detail = str(response.status_code)
            return {
                "success": False,
                "error": f"Generate API failed: {error_detail}",
                "status_code": response.status_code
            }

    except Exception as e:
        return {"success": False, "error": f"Ollama test failed: {str(e)}"}


# 在 test_llm_connection 函数中添加 ollama 分支
def test_llm_connection(llm_config: Dict[str, Any]) -> Dict[str, Any]:
    """测试 LLM 连接"""
    llm_type = llm_config.get("type", "openai").lower()

    try:
        if llm_type == "openai":
            return _test_openai(llm_config)
        elif llm_type == "azure":
            return _test_azure(llm_config)
        elif llm_type == "anthropic":
            return _test_anthropic(llm_config)
        elif llm_type == "ollama":
            return _test_ollama(llm_config)  # 添加 Ollama 测试
        elif llm_type == "custom":
            return _test_custom(llm_config)
        else:
            return {"success": False, "error": f"Unsupported LLM type: {llm_type}"}
    except Exception as e:
        return {"success": False, "error": str(e), "type": type(e).__name__}


# Web 路由
@llm_bp.route('/')
def list_llms():
    """LLM 列表页面"""
    llms = MetaLoader.loads("llms")
    return render_template("llm_list.html", llms=llms, active_page='llm')


@llm_bp.route('/new')
def new_llm():
    """新建 LLM 页面"""
    return render_template("llm_form.html", llm=None, action="create", active_page='llm')


@llm_bp.route('/<id>/edit')
def edit_llm(id):
    """编辑 LLM 页面"""
    llm = MetaLoader.load("llms",id)
    if not llm:
        abort(404)
    return render_template("llm_form.html", llm=llm, action="edit", active_page='llm')


# API 路由
@llm_bp.route('/api/list')
def api_list():
    """获取所有 LLM 配置（API）"""
    llms = MetaLoader.loads("llms")
    return jsonify(llms)


@llm_bp.route('/api/<id>', methods=['GET'])
def api_get(id):
    """获取单个 LLM 配置"""
    llm =MetaLoader.load("llms",id)
    if not llm:
        abort(404)
    return jsonify(llm)


@llm_bp.route('/api', methods=['POST'])
def api_create():
    """创建 LLM 配置"""
    data = request.json
    # 验证配置
    validation_errors = validate_llm_config(data)
    if validation_errors:
        return jsonify({"error": "Validation failed", "errors": validation_errors}), 400



    if not data.get("type"):
        return jsonify({"error": "LLM type is required"}), 400

    # 生成 LLM ID
    id = data.get("id")
    # 保存 LLM
    result=MetaLoader.dump("llms",id, data)
    return jsonify(result)


@llm_bp.route('/api/<id>', methods=['PUT'])
def api_update(id):
    """更新 LLM 配置"""
    data = request.json

    if not data.get("type"):
        return jsonify({"error": "LLM type is required"}), 400

    # 保存更新
    MetaLoader.update("llms",id, data)

    return jsonify({
        "success": True,
        "message": "LLM configuration updated successfully"
    })


@llm_bp.route('/api/<id>', methods=['DELETE'])
def api_delete(id):
    """删除 LLM 配置"""
    if MetaLoader.delete("llms",id):
        return jsonify({
            "success": True,
            "message": "LLM configuration deleted successfully"
        })
    return jsonify({"error": "LLM not found"}), 404


@llm_bp.route('/api/test', methods=['POST'])
def api_test():
    """测试 LLM 连接"""
    data = request.json
    # 验证配置
    validation_errors = validate_llm_config(data)
    if validation_errors:
        return jsonify({"error": "Validation failed", "errors": validation_errors}), 400
    # 执行连接测试
    result = test_llm_connection(data)

    return jsonify(result)



@llm_bp.route('/api/types')
def api_get_types():
    """获取支持的 LLM 类型"""
    types = [
        {"id": "openai", "name": "OpenAI", "description": "OpenAI API (GPT-3.5, GPT-4, etc.)"},
        {"id": "azure", "name": "Azure OpenAI", "description": "Microsoft Azure OpenAI Service"},
        {"id": "anthropic", "name": "Anthropic Claude", "description": "Anthropic Claude API"},
        {"id": "ollama", "name": "Ollama", "description": "Ollama local models (Llama, Mistral, etc.)"},
        {"id": "cohere", "name": "Cohere", "description": "Cohere Generate API"},
        {"id": "huggingface", "name": "HuggingFace", "description": "HuggingFace Inference API"},
        {"id": "custom", "name": "Custom", "description": "Custom LLM API endpoint"}
    ]
    return jsonify(types)


