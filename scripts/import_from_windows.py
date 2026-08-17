import psycopg2
import csv
import json
import os

# 修改为您的密码
conn = psycopg2.connect(
    host="localhost",
    port=5455,          # 容器映射到宿主机的端口
    dbname="zjhx",
    user="postgres",
    password="123456"
)
conn.autocommit = True
cur = conn.cursor()

# 配置：图名与 CSV 文件的路径（Windows 本地绝对路径）
base_dir = r"E:\PythonProject\chuma\docs\sql"  # 请修改为您的实际根目录
graphs = {
    'kg_操作系统_4fd0560e': {
        'vertex': os.path.join(base_dir, 'kg_操作系统_4fd0560e', '_ag_label_vertex.csv'),
        'edge': os.path.join(base_dir, 'kg_操作系统_4fd0560e', '_ag_label_edge.csv')
    },
    'kg_计算机网络_6c4d9cfb': {
        'vertex': os.path.join(base_dir, 'kg_计算机网络_6c4d9cfb', '_ag_label_vertex.csv'),
        'edge': os.path.join(base_dir, 'kg_计算机网络_6c4d9cfb', '_ag_label_edge.csv')
    },
    'kg_计算机组成原理_f6143626': {
        'vertex': os.path.join(base_dir, 'kg_计算机组成原理_f6143626', '_ag_label_vertex.csv'),
        'edge': os.path.join(base_dir, 'kg_计算机组成原理_f6143626', '_ag_label_edge.csv')
    },
    'kg_数据结构_d5e8a43e': {
        'vertex': os.path.join(base_dir, 'kg_数据结构_d5e8a43e', '_ag_label_vertex.csv'),
        'edge': os.path.join(base_dir, 'kg_数据结构_d5e8a43e', '_ag_label_edge.csv')
    },
    'kg_数据库系统概论_2847cbd1': {
        'vertex': os.path.join(base_dir, 'kg_数据库系统概论_2847cbd1', '_ag_label_vertex.csv'),
        'edge': os.path.join(base_dir, 'kg_数据库系统概论_2847cbd1', '_ag_label_edge.csv')
    },
}

# 确保图已存在（如果尚未创建，先创建）
# 您可以提前在 psql 中创建，也可以在这里执行创建，但需要处理重复创建的错误
# 这里我们假设图已经创建好（您之前已创建过）

for graph, files in graphs.items():
    print(f"Processing {graph}...")
    vertex_table = f'"{graph}"."Entity"'
    edge_table = f'"{graph}"."RELATION"'

    # 清空表（避免重复数据）
    try:
        cur.execute(f"TRUNCATE TABLE {vertex_table} CASCADE;")
        cur.execute(f"TRUNCATE TABLE {edge_table} CASCADE;")
    except Exception as e:
        print(f"  Truncate failed (maybe tables empty): {e}")

    # 导入顶点
    vfile = files['vertex']
    if not os.path.exists(vfile):
        print(f"  Vertex file not found: {vfile}, skipping.")
        continue
    with open(vfile, 'r', encoding='utf-8') as f:   # 如果您的源 CSV 是 GBK，请改为 encoding='gbk'
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            # 将 properties 字段解析为 JSON，确保格式正确
            try:
                props_json = json.loads(row['properties'])
                props_clean = json.dumps(props_json, ensure_ascii=False)
            except json.JSONDecodeError:
                props_clean = json.dumps(row['properties'], ensure_ascii=False)
            cur.execute(
                f"INSERT INTO {vertex_table} (id, properties) VALUES (%s, %s::agtype);",
                (row['id'], props_clean)
            )
            count += 1
            if count % 100 == 0:
                print(f"  Inserted {count} vertices...")
    print(f"Vertices imported for {graph} (total {count})")

    # 导入边
    efile = files['edge']
    if not os.path.exists(efile):
        print(f"  Edge file not found: {efile}, skipping.")
        continue
    with open(efile, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            try:
                props_json = json.loads(row['properties'])
                props_clean = json.dumps(props_json, ensure_ascii=False)
            except json.JSONDecodeError:
                props_clean = json.dumps(row['properties'], ensure_ascii=False)
            cur.execute(
                f"INSERT INTO {edge_table} (id, start_id, end_id, properties) VALUES (%s, %s, %s, %s::agtype);",
                (row['id'], row['start_id'], row['end_id'], props_clean)
            )
            count += 1
            if count % 100 == 0:
                print(f"  Inserted {count} edges...")
    print(f"Edges imported for {graph} (total {count})")

conn.close()
print("All graphs imported successfully!")