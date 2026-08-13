"""离线脚本：训练 GNN 推荐模型

用法: python scripts/train_gnn.py --kg data/kg/ --output data/models/
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="训练 GNN 模型")
    parser.add_argument("--kg", required=True, help="知识图谱数据目录")
    parser.add_argument("--output", required=True, help="模型输出目录")
    args = parser.parse_args()
    # TODO: 实现 GNN 训练流程
    print(f"使用知识图谱 {args.kg} 训练模型，输出到 {args.output}")


if __name__ == "__main__":
    main()
