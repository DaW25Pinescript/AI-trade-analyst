"""
Lens contract tests.

Verifies:
- All referenced lens files exist on disk.
- Forbidden terminology does not appear in lenses that ban it.
- Mandatory output fields are declared in each active lens prompt.
- load_active_lens_contracts raises when all lenses are disabled.
- Version selection: v1.2 lenses load independently of v1.1 defaults.
"""
import pytest
from pathlib import Path
from ..core.lens_loader import (
    LENS_DIR, LENS_FILE_MAP, PROMPT_LIBRARY_VERSION, _PROMPT_LIBRARY_ROOT,
    load_active_lens_contracts,
)
from ..models.lens_config import LensConfig

V1_2_LENS_DIR = _PROMPT_LIBRARY_ROOT / "v1.2" / "lenses"

# Lenses that forbid "support" and "resistance"
LENSES_WITH_FORBIDDEN_TERMS = {
    "ict_icc.txt",
    "market_structure.txt",
    "orderflow_lite.txt",
    "trendlines.txt",
    "smt_divergence.txt",
    "harmonic.txt",
    "volume_profile.txt",
}

FORBIDDEN_TERMS_IN_FORBIDDEN_LENSES = ["support", "resistance"]


class TestLensFilesExist:
    def test_all_mapped_lens_files_exist(self):
        missing = [
            filename
            for filename in LENS_FILE_MAP.values()
            if not (LENS_DIR / filename).exists()
        ]
        assert not missing, f"Missing lens files: {missing}"


class TestForbiddenTerminology:
    @pytest.mark.parametrize("filename", sorted(LENSES_WITH_FORBIDDEN_TERMS))
    def test_forbidden_terms_not_in_body(self, filename: str):
        """
        Lenses that declare FORBIDDEN TERMINOLOGY must not use those terms
        in their instructional body text (outside of the FORBIDDEN list itself).
        """
        content = (LENS_DIR / filename).read_text(encoding="utf-8")
        lines = content.splitlines()

        # Find the line index where the FORBIDDEN block starts
        forbidden_block_start = next(
            (i for i, line in enumerate(lines) if "FORBIDDEN TERMINOLOGY" in line),
            len(lines),
        )

        # Only check body lines before the forbidden block
        body = "\n".join(lines[:forbidden_block_start]).lower()

        for term in FORBIDDEN_TERMS_IN_FORBIDDEN_LENSES:
            assert term not in body, (
                f"Lens '{filename}' uses forbidden term '{term}' in its body "
                f"(before the FORBIDDEN TERMINOLOGY section)."
            )


class TestMandatoryFields:
    @pytest.mark.parametrize("filename,required_field", [
        ("ict_icc.txt", "sweep_status"),
        ("ict_icc.txt", "fvg_zones"),
        ("ict_icc.txt", "displacement_quality"),
        ("market_structure.txt", "htf_structure"),
        ("market_structure.txt", "ltf_structure"),
        ("orderflow_lite.txt", "dominant_flow"),
        ("orderflow_lite.txt", "absorption_evidence"),
        ("trendlines.txt", "active_trendlines"),
        ("smt_divergence.txt", "smt_detected"),
        ("harmonic.txt", "pattern_identified"),
        ("harmonic.txt", "prz_zone"),
        ("volume_profile.txt", "poc_level"),
        ("volume_profile.txt", "va_high"),
        ("volume_profile.txt", "va_low"),
    ])
    def test_mandatory_field_declared(self, filename: str, required_field: str):
        content = (LENS_DIR / filename).read_text(encoding="utf-8")
        assert required_field in content, (
            f"Lens '{filename}' does not declare mandatory field '{required_field}'."
        )


class TestLensLoader:
    def test_raises_when_no_lenses_enabled(self):
        config = LensConfig(
            ICT_ICC=False,
            MarketStructure=False,
            OrderflowLite=False,
            Trendlines=False,
            ClassicalIndicators=False,
            Harmonic=False,
            SMT_Divergence=False,
            VolumeProfile=False,
        )
        with pytest.raises(ValueError, match="At least one lens"):
            load_active_lens_contracts(config)

    def test_loads_single_lens(self):
        config = LensConfig(ICT_ICC=True, MarketStructure=False)
        result = load_active_lens_contracts(config)
        assert "ICT/ICC" in result
        assert "Market Structure" not in result

    def test_loads_multiple_lenses_separated(self):
        config = LensConfig(ICT_ICC=True, MarketStructure=True)
        result = load_active_lens_contracts(config)
        assert "ICT/ICC" in result
        assert "Market Structure" in result
        assert "---" in result   # separator between blocks


class TestV12LensFiles:
    """v1.2 lens files exist and contain required v1.2 additions."""

    def test_all_v12_lens_files_exist(self):
        missing = [
            filename
            for filename in LENS_FILE_MAP.values()
            if not (V1_2_LENS_DIR / filename).exists()
        ]
        assert not missing, f"Missing v1.2 lens files: {missing}"

    @pytest.mark.parametrize("filename", sorted(LENS_FILE_MAP.values()))
    def test_v12_lens_has_metadata_block(self, filename: str):
        content = (V1_2_LENS_DIR / filename).read_text(encoding="utf-8")
        assert "METADATA:" in content, (
            f"v1.2 lens '{filename}' is missing METADATA block "
            f"(minimum_confidence_threshold required)."
        )

    @pytest.mark.parametrize("filename", sorted(LENS_FILE_MAP.values()))
    def test_v12_lens_has_confidence_threshold(self, filename: str):
        content = (V1_2_LENS_DIR / filename).read_text(encoding="utf-8")
        assert "minimum_confidence_threshold" in content, (
            f"v1.2 lens '{filename}' does not declare minimum_confidence_threshold."
        )

    @pytest.mark.parametrize("filename", sorted(LENS_FILE_MAP.values()))
    def test_v12_lens_has_examples_section(self, filename: str):
        content = (V1_2_LENS_DIR / filename).read_text(encoding="utf-8")
        assert "EXAMPLES:" in content, (
            f"v1.2 lens '{filename}' is missing EXAMPLES section."
        )

    @pytest.mark.parametrize("filename", sorted(LENS_FILE_MAP.values()))
    def test_v12_lens_has_positive_and_negative_examples(self, filename: str):
        content = (V1_2_LENS_DIR / filename).read_text(encoding="utf-8")
        assert "POSITIVE" in content, (
            f"v1.2 lens '{filename}' EXAMPLES section missing POSITIVE example."
        )
        assert "NEGATIVE" in content, (
            f"v1.2 lens '{filename}' EXAMPLES section missing NEGATIVE example."
        )

    # All v1.2 lenses (except classical_indicators, which explicitly permits the terms)
    # must not use "support" or "resistance" in their instructional body.
    V12_FORBIDDEN_LENSES = {
        "ict_icc.txt",
        "market_structure.txt",
        "orderflow_lite.txt",
        "trendlines.txt",
        "smt_divergence.txt",
        "harmonic.txt",
        "volume_profile.txt",
    }

    @pytest.mark.parametrize("filename", sorted(V12_FORBIDDEN_LENSES))
    def test_v12_forbidden_terms_not_in_body(self, filename: str):
        content = (V1_2_LENS_DIR / filename).read_text(encoding="utf-8")
        lines = content.splitlines()
        forbidden_block_start = next(
            (i for i, line in enumerate(lines) if "FORBIDDEN TERMINOLOGY" in line),
            len(lines),
        )
        body = "\n".join(lines[:forbidden_block_start]).lower()
        for term in ["support", "resistance"]:
            assert term not in body, (
                f"v1.2 lens '{filename}' uses forbidden term '{term}' in body "
                f"(before the FORBIDDEN TERMINOLOGY section)."
            )


class TestVersionSelection:
    """load_active_lens_contracts version parameter selects correct library."""

    def test_default_version_loads_v11(self):
        config = LensConfig(ICT_ICC=True)
        result = load_active_lens_contracts(config)
        # v1.1 ict_icc.txt does not have METADATA block
        assert "METADATA:" not in result

    def test_explicit_v11_loads_v11(self):
        config = LensConfig(ICT_ICC=True)
        result = load_active_lens_contracts(config, version="v1.1")
        assert "METADATA:" not in result

    def test_explicit_v12_loads_v12(self):
        config = LensConfig(ICT_ICC=True)
        result = load_active_lens_contracts(config, version="v1.2")
        assert "METADATA:" in result
        assert "minimum_confidence_threshold" in result
        assert "EXAMPLES:" in result

    def test_v12_and_v11_are_independent(self):
        config = LensConfig(ICT_ICC=True)
        v11 = load_active_lens_contracts(config, version="v1.1")
        v12 = load_active_lens_contracts(config, version="v1.2")
        assert v11 != v12

    def test_raises_on_unknown_version(self):
        config = LensConfig(ICT_ICC=True)
        with pytest.raises(FileNotFoundError, match="prompt_library/v9.9/lenses"):
            load_active_lens_contracts(config, version="v9.9")

    def test_v12_multi_lens_separator_present(self):
        config = LensConfig(ICT_ICC=True, MarketStructure=True)
        result = load_active_lens_contracts(config, version="v1.2")
        assert "---" in result
        assert "ICT/ICC" in result
        assert "Market Structure" in result

    def test_default_version_constant_is_v11(self):
        assert PROMPT_LIBRARY_VERSION == "v1.1"
