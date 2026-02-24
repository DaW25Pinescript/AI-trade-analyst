from pydantic import BaseModel


class LensConfig(BaseModel):
    ICT_ICC: bool = True
    MarketStructure: bool = True
    OrderflowLite: bool = False
    Trendlines: bool = False
    ClassicalIndicators: bool = False
    Harmonic: bool = False
    SMT_Divergence: bool = False
    VolumeProfile: bool = False

    def active_lens_names(self) -> list[str]:
        """Return the list of enabled lens field names."""
        return [name for name, enabled in self.model_dump().items() if enabled]
