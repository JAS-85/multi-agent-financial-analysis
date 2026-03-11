import json
import tempfile
from pathlib import Path

import pytest

from utils.pdf_reader import read_text_file, read_document
from utils.data_formatter import format_result, merge_results, truncate_text


class TestPdfReader:
    def test_read_text_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello world", encoding="utf-8")
        assert read_text_file(str(f)) == "Hello world"

    def test_read_text_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_text_file("nonexistent.txt")

    def test_read_document_txt(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("some data", encoding="utf-8")
        assert read_document(str(f)) == "some data"

    def test_read_document_csv(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("col1,col2\n1,2", encoding="utf-8")
        result = read_document(str(f))
        assert "col1" in result

    def test_read_document_unsupported(self, tmp_path):
        f = tmp_path / "data.xlsx"
        f.write_text("data", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            read_document(str(f))


class TestDataFormatter:
    def test_format_result(self):
        data = {"key": "value"}
        formatted = format_result(data)
        assert json.loads(formatted) == data

    def test_merge_results(self):
        results = {
            "agent1": {"data": "test1"},
            "agent2": {"data": "test2"},
        }
        merged = merge_results(results)
        assert "agent1" in merged
        assert merged["agent1"]["data"] == "test1"

    def test_merge_results_non_dict(self):
        results = {"agent1": "plain string"}
        merged = merge_results(results)
        assert merged["agent1"] == {"raw_response": "plain string"}

    def test_truncate_short_text(self):
        text = "Short text."
        assert truncate_text(text, 100) == text

    def test_truncate_long_text(self):
        text = "First sentence. Second sentence. Third sentence. " * 20
        result = truncate_text(text, 100)
        assert len(result) < len(text)
        assert result.endswith("[... truncated]")
