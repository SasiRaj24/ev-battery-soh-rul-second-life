"""Model lifecycle boundary; evaluation artifacts are not deployable models."""

from .schemas import ModelStatus


class ModelRegistry:
    """Expose deployment readiness without loading evaluation-fold models."""

    def list_status(self) -> list[ModelStatus]:
        return [
            ModelStatus(
                model="persistence",
                role="evaluation_baseline",
                deployed=False,
                details=(
                    "Available as a measured validation comparator; no standalone "
                    "production inference model is registered."
                ),
            ),
            ModelStatus(
                model="linear_regression",
                role="cross_battery_evaluation",
                deployed=False,
                details=(
                    "Fold-specific models were fitted for offline evaluation and "
                    "were not saved as deployable artifacts."
                ),
            ),
            ModelStatus(
                model="xgboost",
                role="cross_battery_evaluation",
                deployed=False,
                details=(
                    "Fold-specific models were fitted for offline evaluation and "
                    "were not saved as deployable artifacts."
                ),
            ),
        ]
