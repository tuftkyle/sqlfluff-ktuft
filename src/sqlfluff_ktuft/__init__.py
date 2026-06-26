"""Personal SQLFluff rules for KTuft SQL layout preferences."""

from sqlfluff.core.plugin import hookimpl


@hookimpl
def get_rules():
    """Expose personal SQLFluff rules."""
    from sqlfluff_ktuft.rules import (
        Rule_Ktuft_KL01,
        Rule_Ktuft_KL02,
        Rule_Ktuft_KL03,
        Rule_Ktuft_KL04,
        Rule_Ktuft_KL05,
        Rule_Ktuft_KL06,
        Rule_Ktuft_KL07,
        Rule_Ktuft_KL08,
        Rule_Ktuft_KL09,
        Rule_Ktuft_KL10,
        Rule_Ktuft_KL11,
        Rule_Ktuft_KL12,
        Rule_Ktuft_KL13,
        Rule_Ktuft_KL14,
        Rule_Ktuft_KL15,
        Rule_Ktuft_KL16,
        Rule_Ktuft_KL17,
        Rule_Ktuft_KL18,
        Rule_Ktuft_KL19,
    )

    return [
        Rule_Ktuft_KL01,
        Rule_Ktuft_KL02,
        Rule_Ktuft_KL03,
        Rule_Ktuft_KL04,
        Rule_Ktuft_KL05,
        Rule_Ktuft_KL06,
        Rule_Ktuft_KL07,
        Rule_Ktuft_KL08,
        Rule_Ktuft_KL09,
        Rule_Ktuft_KL10,
        Rule_Ktuft_KL11,
        Rule_Ktuft_KL12,
        Rule_Ktuft_KL13,
        Rule_Ktuft_KL14,
        Rule_Ktuft_KL15,
        Rule_Ktuft_KL16,
        Rule_Ktuft_KL17,
        Rule_Ktuft_KL18,
        Rule_Ktuft_KL19,
    ]


@hookimpl
def load_default_config():
    """Load plugin default config."""
    return {}


@hookimpl
def get_configs_info():
    """Describe plugin config options."""
    return {}
