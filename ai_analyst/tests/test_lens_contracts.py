"""
Lens contract tests.

Verifies:
- All referenced lens files exist on disk.
- Forbidden terminology does not appear in lenses that ban it.
- Mandatory output fields are declared in each active lens prompt.
- load_active_lens_contracts raises when all lenses are disabled.
"""
import pytest
from pathlib import Path
from ..core.lens_loader import LENS_DIR, LENS_FILE_MAP, load_active_lens_contracts
from ..models.lens_config import LensConfig

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
