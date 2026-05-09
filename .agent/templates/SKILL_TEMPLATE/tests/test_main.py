#!/usr/bin/env python3
"""
Tests para la skill.

Uso:
    python -m pytest tests/test_main.py -v
    python -m pytest tests/test_main.py --cov=scripts
"""

import json
import sys
from pathlib import Path

import pytest

# Agregar scripts al path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from main import process_data, validate_input, SkillResult


class TestProcessData:
    """Tests para la función process_data."""

    def test_basic_processing(self):
        """Test de procesamiento básico."""
        result = process_data("hello world")

        assert result.status == "success"
        assert result.data["input_length"] == 11
        assert result.data["word_count"] == 2
        assert result.data["processed"] == "HELLO WORLD"

    def test_empty_input(self):
        """Test con entrada vacía."""
        result = process_data("")

        assert result.status == "success"
        assert result.data["input_length"] == 0

    def test_verbose_mode(self):
        """Test con modo verbose."""
        result = process_data("test", verbose=True)

        assert result.status == "success"
        assert "details" in result.data
        assert result.data["details"]["original"] == "test"

    def test_different_formats(self):
        """Test con diferentes formatos."""
        for format in ["json", "text", "markdown"]:
            result = process_data("test", format=format)
            assert result.status == "success"
            assert result.metadata["format"] == format

    def test_metadata_includes_timestamp(self):
        """Test que metadata incluye timestamp."""
        result = process_data("test")

        assert "timestamp" in result.metadata
        assert "duration_ms" in result.metadata


class TestSkillResult:
    """Tests para la clase SkillResult."""

    def test_to_dict(self):
        """Test conversión a diccionario."""
        result = SkillResult(
            status="success", data={"key": "value"}, metadata={"timestamp": "2026-01-01"}
        )

        d = result.to_dict()
        assert d["status"] == "success"
        assert d["data"]["key"] == "value"

    def test_to_json(self):
        """Test conversión a JSON."""
        result = SkillResult(status="success", data={"key": "value"}, metadata={})

        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert parsed["status"] == "success"


class TestValidateInput:
    """Tests para validación de entrada."""

    def test_missing_input(self):
        """Test con input faltante."""

        class Args:
            input = None
            format = "json"

        error = validate_input(Args())
        assert error is not None
        assert "input" in error.lower()

    def test_invalid_format(self):
        """Test con formato inválido."""

        class Args:
            input = "test"
            format = "invalid"

        error = validate_input(Args())
        assert error is not None
        assert "formato" in error.lower()

    def test_valid_input(self):
        """Test con entrada válida."""

        class Args:
            input = "test"
            format = "json"

        error = validate_input(Args())
        assert error is None


# Fixtures para tests más complejos
@pytest.fixture
def sample_input():
    """Proporciona datos de ejemplo para tests."""
    return "Este es un texto de ejemplo para testing."


@pytest.fixture
def expected_output(sample_input):
    """Proporciona salida esperada."""
    return {"input_length": len(sample_input), "word_count": 8, "processed": sample_input.upper()}


class TestIntegration:
    """Tests de integración."""

    def test_full_pipeline(self, sample_input, expected_output):
        """Test del pipeline completo."""
        result = process_data(sample_input)

        assert result.status == "success"
        assert result.data["input_length"] == expected_output["input_length"]
        assert result.data["word_count"] == expected_output["word_count"]

    def test_json_output_is_valid(self, sample_input):
        """Test que el JSON de salida es válido."""
        result = process_data(sample_input)
        json_output = result.to_json()

        # Debe poder parsearse sin errores
        parsed = json.loads(json_output)
        assert parsed["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
