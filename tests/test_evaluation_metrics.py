import unittest
import json
import tempfile
from pathlib import Path

from evaluation.dataset import load_dataset
from evaluation.metrics import answer_metrics, evidence_match, is_abstention, retrieval_metrics, token_prf
from evaluation.reporting import build_summary, percentile, write_reports


class EvaluationMetricsTests(unittest.TestCase):
    def test_token_prf_perfect_match(self):
        result = token_prf("etcd uses client port 2379", "etcd uses client port 2379")
        self.assertEqual(result["f1"], 1.0)
        self.assertEqual(result["precision"], 1.0)
        self.assertEqual(result["recall"], 1.0)

    def test_abstention_detection(self):
        self.assertTrue(is_abstention("I cannot answer based on the provided documents."))
        self.assertTrue(is_abstention(""))
        self.assertFalse(is_abstention("Kubernetes uses Pods to run containers."))

    def test_percentile(self):
        self.assertEqual(percentile([100.0, 300.0], 0.50), 200.0)
        self.assertEqual(percentile([100.0, 300.0], 0.95), 290.0)
        self.assertIsNone(percentile([], 0.95))

    def test_evidence_match(self):
        self.assertTrue(evidence_match(
            "etcd stores state on client port 2379 and peer port 2380",
            ["client port 2379 and peer port 2380"],
        ))
        self.assertFalse(evidence_match("Pods use an IP address", ["etcd port 2379"]))

    def test_retrieval_metrics(self):
        rows = [
            {"chunk_id": "a", "filename": "architecture.md"},
            {"chunk_id": "b", "filename": "other.md"},
        ]
        result = retrieval_metrics(rows, {"a"}, {"architecture.md"}, 2)
        self.assertEqual(result["precision_at_k"], 0.5)
        self.assertEqual(result["recall_at_k"], 1.0)
        self.assertEqual(result["mrr_at_k"], 1.0)
        self.assertEqual(result["document_recall_at_k"], 1.0)
        self.assertEqual(result["document_precision_at_k"], 0.5)

    def test_source_citation_recall_requires_all_expected_documents(self):
        result = answer_metrics(
            answer="The answer is supported [S1].",
            reference_answer="supported answer",
            answer_key_terms=["supported"],
            retrieved_context="supported answer evidence",
            citations=[{"source_id": "S1", "filename": "one.md"}],
            relevant_documents={"one.md", "two.md"},
            is_answerable=True,
        )
        self.assertEqual(result["source_citation_recall"], 0.5)
        self.assertFalse(result["correct_document_citation"])

    def test_answerable_abstention_is_incorrect(self):
        result = answer_metrics(
            answer="I cannot answer based on the provided documents.",
            reference_answer="etcd stores cluster state",
            answer_key_terms=["etcd", "cluster state"],
            retrieved_context="etcd stores cluster state",
            citations=[],
            relevant_documents={"architecture.md"},
            is_answerable=True,
        )
        self.assertTrue(result["abstained"])
        self.assertFalse(result["abstention_correct"])

    def test_unanswerable_abstention(self):
        result = answer_metrics(
            answer="I cannot answer based on the provided documents.",
            reference_answer="",
            answer_key_terms=[],
            retrieved_context="unrelated content",
            citations=[],
            relevant_documents=set(),
            is_answerable=False,
        )
        self.assertTrue(result["abstained"])
        self.assertTrue(result["abstention_correct"])

    def test_sample_dataset_loads(self):
        path = Path("evaluation/datasets/sample_rag_dataset.jsonl")
        cases = load_dataset(path)
        self.assertEqual(len(cases), 18)
        self.assertTrue(any(not case["is_answerable"] for case in cases))

    def test_summary_includes_boolean_metrics(self):
        summary = build_summary([
            {"strategy": "hybrid", "is_answerable": False, "retrieved_chunks": 0,
             "abstention_correct": True, "retrieval_latency_ms": 20.0}
        ])
        self.assertEqual(summary["hybrid"]["abstention_correct"], 1.0)

    def test_generation_latency_summary_excludes_fallbacks_and_failures(self):
        summary = build_summary([
            {"strategy": "vector", "is_answerable": True, "retrieved_chunks": 1,
             "llm_generation_attempted": True, "llm_generation_succeeded": True,
             "llm_generation_failed": False, "answer_generated": True,
             "generation_latency_ms": 100.0},
            {"strategy": "vector", "is_answerable": True, "retrieved_chunks": 1,
             "llm_generation_attempted": True, "llm_generation_succeeded": True,
             "llm_generation_failed": False, "answer_generated": True,
             "generation_latency_ms": 300.0},
            {"strategy": "vector", "is_answerable": True, "retrieved_chunks": 1,
             "llm_generation_attempted": True, "llm_generation_succeeded": False,
             "llm_generation_failed": True, "answer_generated": False,
             "generation_latency_ms": 900.0, "answer_error": "timeout"},
            {"strategy": "vector", "is_answerable": False, "retrieved_chunks": 0,
             "llm_generation_attempted": False, "llm_generation_succeeded": False,
             "llm_generation_failed": False, "answer_generated": True,
             "generation_latency_ms": None},
        ])["vector"]
        self.assertEqual(summary["llm_generation_attempts"], 3)
        self.assertEqual(summary["answer_generation_successes"], 2)
        self.assertEqual(summary["answer_generation_failures"], 1)
        self.assertEqual(summary["mean_generation_latency_ms"], 200.0)
        self.assertEqual(summary["median_generation_latency_ms"], 200.0)
        self.assertEqual(summary["p95_generation_latency_ms"], 290.0)
        self.assertEqual(summary["mean_failed_generation_latency_ms"], 900.0)
        self.assertEqual(summary["answers_returned_including_fallback"], 3)

    def test_reports_are_written(self):
        case = {
            "case_id": "sample_1", "strategy": "hybrid", "question": "test?",
            "is_answerable": True, "retrieved_chunks": 1, "answer_generated": True,
            "answer": "answer", "retrieval_latency_ms": 2.0, "generation_latency_ms": 3.0,
            "precision_at_k": 0.2, "recall_at_k": 1.0, "mrr_at_k": 1.0,
            "ndcg_at_k": 1.0, "document_precision_at_k": 1.0,
            "document_recall_at_k": 1.0, "reference_token_f1": 0.8,
            "abstention_correct": True,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_reports(Path(temp_dir), "test_run", {"case_count": 1, "top_k": 5}, [case])
            self.assertTrue(Path(paths["json"]).is_file())
            self.assertTrue(Path(paths["csv"]).is_file())
            self.assertTrue(Path(paths["markdown"]).is_file())
            payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["hybrid"]["cases"], 1)
    def test_abstention_phrase_inside_substantive_answer_is_not_abstention(self):
        answer = (
            'According to [S1], Deployments support rollbacks. '
            'The system response also contained the quote '
            '"I cannot answer based on the provided documents."'
        )

        self.assertFalse(is_abstention(answer))

    def test_abstention_with_explanation_is_detected(self):
        answer = (
            "I cannot answer based on the provided documents. "
            "The required information is missing."
        )

        self.assertTrue(is_abstention(answer))

    def test_mrr_uses_first_relevant_result(self):
        rows = [
            {"chunk_id": "relevant_1", "filename": "architecture.md"},
            {"chunk_id": "irrelevant", "filename": "other.md"},
            {"chunk_id": "relevant_2", "filename": "architecture.md"},
        ]

        result = retrieval_metrics(
            rows,
            {"relevant_1", "relevant_2"},
            {"architecture.md"},
            3,
        )

        self.assertEqual(result["mrr_at_k"], 1.0)

    def test_mrr_uses_rank_of_first_relevant_result(self):
        rows = [
            {"chunk_id": "irrelevant", "filename": "other.md"},
            {"chunk_id": "relevant_1", "filename": "architecture.md"},
            {"chunk_id": "relevant_2", "filename": "architecture.md"},
        ]

        result = retrieval_metrics(
            rows,
            {"relevant_1", "relevant_2"},
            {"architecture.md"},
            3,
        )

        self.assertEqual(result["mrr_at_k"], 0.5)

if __name__ == "__main__":
    unittest.main()
