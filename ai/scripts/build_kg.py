"""离线脚本：从教材/课件构建知识图谱

用法: python scripts/build_kg.py --input data/textbooks/ --output data/kg/
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="构建学科知识图谱")
    parser.add_argument("--input", required=True, help="教材文本目录")
    parser.add_argument("--output", required=True, help="知识图谱输出目录")
    args = parser.parse_args()
    # TODO: 实现 LLM 辅助的知识图谱构建流程
    print(f"从 {args.input} 构建知识图谱，输出到 {args.output}")


if __name__ == "__main__":
    main()
