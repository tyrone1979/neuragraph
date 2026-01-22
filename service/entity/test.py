from typing import Any
from logging import getLogger

import csv
from pathlib import Path
from data.ctd_parser import parse
from service.entity.entity import EntityLoader

TEST_DIR = Path(__file__).resolve().parent.parent.parent  / "tests"
logger = getLogger(__name__)


class TestLoader(EntityLoader):

    @staticmethod
    def load_by_id_file(id:str,file:str) -> None | tuple[list[Any], list[Any]] | tuple[list[Any], list]:
        test_path = TEST_DIR / id
        test_path.mkdir(parents=True, exist_ok=True)
        test_file = test_path / file
        if '.csv' in file:
            with open(test_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                return list(rows[0].keys()), rows
        elif '.txt' in file:
            articles = parse(test_file.read_text(encoding='utf-8'))
            field_names = list(articles[0].__dataclass_fields__.keys()) if articles else []
            return field_names, articles
        return [], []

    @staticmethod
    def load_by_graph(graph, test_sets):
        graph_test_set_dir = TEST_DIR / graph['id']
        if not graph['id'] in test_sets:
            test_sets[graph['id']] = {}
        if graph_test_set_dir.exists():
            for test_file in graph_test_set_dir.iterdir():
                if test_file.is_file() and test_file.name.endswith(".csv"):
                    with open(test_file, mode='r', newline='', encoding='utf-8') as csvfile:
                        reader = csv.reader(csvfile)
                        test_sets[graph['id']][test_file.name] = list(reader)
        for agent in graph['nodes']:
            test_sets[agent] = {}
            if agent in ['START', 'END']:
                continue
            agent_test_set_dir = TEST_DIR / agent
            if agent_test_set_dir.exists():
                for test_file in agent_test_set_dir.iterdir():
                    if test_file.is_file() and test_file.name.endswith(".csv"):
                        with open(test_file, mode='r', newline='', encoding='utf-8') as csvfile:
                            reader = csv.reader(csvfile)
                            test_sets[agent][test_file.name] = list(reader)
        return test_sets


    @staticmethod
    def load_by_id(agent_name: str) -> dict[str, dict[str, str]]:
        """
        加载 agent_name 下的所有 CSV 测试数据集
        每个 CSV 默认只有 2 行：第一行 header，第二行数据
        返回格式: {filename: {col1: value1, col2: value2, ...}}
        """
        test_sets = {}
        test_dir = TEST_DIR / agent_name

        if not test_dir.exists():
            return test_sets  # 目录不存在返回空

        for test_file in test_dir.iterdir():
            if test_file.is_file() and test_file.suffix.lower() == ".csv":
                try:
                    with open(test_file, mode='r', newline='', encoding='utf-8') as csvfile:
                        # DictReader 自动把第一行当 header
                        reader = csv.DictReader(csvfile)
                        rows = list(reader)

                        if len(rows) == 0:
                            # 空文件，跳过或给空 dict
                            test_sets[test_file.name] = {}
                            continue

                        # 只取第一行数据（你的默认场景）
                        first_row = rows[0]

                        # 转成普通 dict，去掉可能的空白 key/value
                        cleaned_row = {k.strip(): v.strip() for k, v in first_row.items() if k}

                        test_sets[test_file.name] = cleaned_row

                except Exception as e:
                    print(f"[WARN] Load failed {test_file.name}: {e}")
                    continue

        return test_sets

    @staticmethod
    def loads():
        """加载所有测试数据集（兼容CSV格式）"""
        tests = []

        # 遍历所有agent目录
        for agent_dir in TEST_DIR.iterdir():
            if not agent_dir.is_dir():
                continue
            agent_id = agent_dir.name
            tests = tests + TestLoader.get_by_agent(agent_id)

        return sorted(tests, key=lambda x: x.get("agent_id", "").lower())

    @staticmethod
    def get_one(agent_id: str, test_id: str):
        """获取单个测试数据集"""
        csv_file = TEST_DIR / agent_id / f"{test_id}.csv"

        if not csv_file.exists():
            return None

        try:
            # 读取CSV文件
            with open(csv_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                if len(rows) == 0:
                    return None

                # 取第一行数据（默认场景）
                first_row = rows[0]
                cleaned_row = {}
                for key, value in first_row.items():
                    if key and key.strip():
                        cleaned_row[key.strip()] = value.strip() if value else ""

                # 构建基本数据
                test_data = {
                    "id": test_id,
                    "name": test_id,
                    "agent_id": agent_id,
                    "inputs": cleaned_row,
                    "file_path": str(csv_file)
                }

                return test_data

        except Exception as e:
            print(f"[ERROR] Failed to load test {test_id}: {e}")
            return None

    @staticmethod
    def save(agent_id: str, test_id: str, data: dict):
        """保存测试数据集到CSV文件"""
        # 确保agent目录存在
        agent_dir = TEST_DIR / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        csv_file = agent_dir / f"{test_id}.csv"

        # 分离数据和元数据
        inputs_data = data.get("inputs", {})

        # 保存CSV文件
        if inputs_data:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                # 使用字典的键作为CSV的header
                fieldnames = list(inputs_data.keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(inputs_data)
        else:
            # 如果没有输入数据，创建一个空CSV
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                f.write("")  # 创建空文件



    @staticmethod
    def get_by_agent(agent_id: str):
        """根据agent_id获取相关测试数据集"""
        agent_dir = TEST_DIR / agent_id
        tests = []

        if not agent_dir.exists():
            return tests

        # 遍历该agent下的所有CSV文件
        for csv_file in agent_dir.glob("*.csv"):
            try:
                test_id = csv_file.stem  # 文件名（不含扩展名）作为test_id

                # 读取CSV文件
                with open(csv_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    row_count = len(rows)
                    if row_count == 0:
                        # 空文件，跳过
                        continue

                    # 取第一行数据（默认场景）
                    first_row = rows[0]

                    # 清理数据
                    cleaned_row = {}
                    for key, value in first_row.items():
                        if key and key.strip():  # 确保key不为空
                            cleaned_row[key.strip()] = value.strip() if value else ""

                    # 构建测试数据集对象
                    test_data = {
                        "id": test_id,
                        "name": csv_file.name,  # 默认用文件名作为name
                        "agent_id": agent_id,
                        "inputs": cleaned_row,
                        "count": row_count,

                    }

                    tests.append(test_data)

            except Exception as e:
                print(f"[ERROR] Load test {csv_file.name} failed: {e}")

        for txt_file in agent_dir.glob("*.txt"):
            try:
                test_id = txt_file.stem
                txt_path = agent_dir / f"{test_id}.txt"
                articles = parse(txt_path.read_text(encoding='utf-8'))
                test_data = {
                    "id": test_id,
                    "name": txt_file.name,  # 默认用文件名作为name
                    "agent_id": agent_id,
                    "inputs": {"doc_id": "", "entities": "", "relations": ""},
                    "count": len(articles),
                }
                tests.append(test_data)
            except Exception as e:
                print(f"[ERROR] Load test {txt_file.name} failed: {e}")

        return sorted(tests, key=lambda x: x.get("name", "").lower())

    @staticmethod
    def delete(agent_id:str, test_id: str):
        """删除测试数据集"""
        csv_file = TEST_DIR / agent_id / f"{test_id}.csv"
        if csv_file.exists():
            csv_file.unlink()
            return True
        return False

    @staticmethod
    def count():
        total=0
        # 遍历所有agent目录
        for agent_dir in TEST_DIR.iterdir():
            if not agent_dir.is_dir():
                    continue
            count_txt=len(list(agent_dir.glob("*.txt")))
            count_csv=len(list(agent_dir.glob("*.csv")))
            total+=count_txt+count_csv
        return total