
from pathlib import Path
from typing import Iterable

from app.analysis.extraction import (
    ExtractionRequest,
    ExtractionResult,
    FinancialDataExtractor,
)
from app.analysis.sec_adapter import SECXBRLExtractor


class ExtractorRegistry:
    """
    Registry that selects financial data extractors
    based on supported file extensions.
    """

    def __init__(
        self,
        extractors: Iterable[FinancialDataExtractor] = (),
    ):
        self._extractors: dict[str, FinancialDataExtractor] = {}

        for extractor in extractors:
            self.register(extractor)

    def register(self, extractor: FinancialDataExtractor) -> None:
        """
        Register an extractor for its supported extensions.
        """

        for extension in extractor.supported_extensions:
            normalized_extension = extension.lower()

            if not normalized_extension.startswith("."):
                raise ValueError(
                    f"Invalid file extension: {extension}"
                )

            if normalized_extension in self._extractors:
                raise ValueError(
                    f"An extractor is already registered "
                    f"for {normalized_extension}"
                )

            self._extractors[normalized_extension] = extractor

    def get_extractor(
        self,
        file_path: str | Path,
    ) -> FinancialDataExtractor:
        """
        Return the appropriate extractor for a file.
        """

        extension = Path(file_path).suffix.lower()

        extractor = self._extractors.get(extension)

        if extractor is None:
            raise ValueError(
                f"No financial extractor registered "
                f"for file extension: {extension or 'unknown'}"
            )

        return extractor

    def extract(
        self,
        request: ExtractionRequest,
    ) -> ExtractionResult:
        """
        Select an extractor and execute the extraction request.
        """

        extractor = self.get_extractor(request.file_path)

        return extractor.extract(request)


def create_default_registry() -> ExtractorRegistry:
    """
    Create the default registry with available extractors.
    """

    return ExtractorRegistry(
        extractors=[
            SECXBRLExtractor(),
        ]
    )
