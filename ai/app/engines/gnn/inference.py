"""GNN 推理"""


class GNNInference:
    """GNN 推理引擎"""

    def recommend_questions(self, student_id: int, top_k: int = 10) -> list[dict]:
        """为学生推荐题目"""
        pass

    def recommend_lesson_plan(self, class_id: int) -> dict:
        """为教师推荐教案"""
        pass
