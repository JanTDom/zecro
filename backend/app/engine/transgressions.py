from typing import List, Dict, Any, Tuple
from ..models.schemas import TransgressionDef, SceneGraph, Element

STANDARD_TRANSGRESSIONS: List[TransgressionDef] = [
    TransgressionDef(
        id="diagonal-break",
        name="Diagonal Tilt / Dynamic Rotation",
        applies_to=["headline", "photo", "band"],
        effect="rotate",
        cost=0.30,
        max_per_page=1,
        precondition="page_energy >= 0.5 AND element.importance >= 0.7",
        range=[-6.0, 6.0]
    ),
    TransgressionDef(
        id="overlap-scrim",
        name="Text-Photo Overlap with Scrim",
        applies_to=["headline", "lead", "deck"],
        effect="overlap",
        cost=0.25,
        max_per_page=2,
        precondition="has_photo_underneath == True",
        range=[10.0, 40.0]  # mm overlap
    ),
    TransgressionDef(
        id="bleed-off",
        name="Bleed Off Page Edge",
        applies_to=["photo", "band"],
        effect="bleed",
        cost=0.20,
        max_per_page=2,
        precondition="element.importance >= 0.6",
        range=[3.0, 5.0]  # mm bleed
    ),
    TransgressionDef(
        id="extreme-scale",
        name="Mega Typographic / Visual Dominance",
        applies_to=["headline", "photo"],
        effect="scale",
        cost=0.30,
        max_per_page=1,
        precondition="element.importance >= 0.85",
        range=[1.2, 1.6]
    ),
    TransgressionDef(
        id="cutout-wrap",
        name="Cutout Object Contour Text Wrap",
        applies_to=["photo"],
        effect="contour_wrap",
        cost=0.35,
        max_per_page=2,
        precondition="element.treatment == 'cutout'",
        range=[2.5, 5.0]  # wrap offset mm
    ),
    TransgressionDef(
        id="grid-break",
        name="Intentional Column Offset",
        applies_to=["pullquote", "infobox", "photo"],
        effect="offset",
        cost=0.15,
        max_per_page=2,
        precondition="element.importance <= 0.8",
        range=[-8.0, 8.0]
    )
]

def get_transgression_catalog() -> Dict[str, TransgressionDef]:
    return {t.id: t for t in STANDARD_TRANSGRESSIONS}

class TransgressionManager:
    def __init__(self, catalog: List[TransgressionDef] = None, budget: float = 0.8):
        self.catalog = {t.id: t for t in (catalog or STANDARD_TRANSGRESSIONS)}
        self.budget = budget

    def calculate_page_energy(self, scene_graph: SceneGraph) -> Tuple[float, List[str]]:
        """
        Calculates total tension energy consumed on the page and returns list of applied transgressions.
        """
        applied = []
        total_energy = 0.0

        for elem in scene_graph.elements:
            if elem.transgressions:
                for t_id in elem.transgressions:
                    if t_id in self.catalog:
                        cost = self.catalog[t_id].cost
                        total_energy += cost
                        applied.append(f"{elem.id}:{t_id} (cost {cost:.2f})")

            # Implicit transgressions detection
            if elem.treatment == "cutout" and elem.text_wrap and elem.text_wrap.mode == "contour":
                if "cutout-wrap" not in (elem.transgressions or []):
                    cost = self.catalog["cutout-wrap"].cost
                    total_energy += cost
                    applied.append(f"{elem.id}:cutout-wrap (cost {cost:.2f})")

            if abs(elem.frame.rotation_deg) > 0.5 and "diagonal-break" not in (elem.transgressions or []):
                cost = self.catalog["diagonal-break"].cost
                total_energy += cost
                applied.append(f"{elem.id}:diagonal-break (cost {cost:.2f})")

        return round(total_energy, 3), applied

    def validate(self, scene_graph: SceneGraph) -> List[str]:
        """Return hard violations for illegal transgressions.

        The generator may explore boldly, but only catalogued effects on
        permitted roles and within per-page quotas reach a renderer.
        """
        violations: List[str] = []
        counts: Dict[str, int] = {}
        for elem in scene_graph.elements:
            for transgression_id in elem.transgressions or []:
                definition = self.catalog.get(transgression_id)
                if definition is None:
                    violations.append(f"Unknown transgression '{transgression_id}' on {elem.id}.")
                    continue
                counts[transgression_id] = counts.get(transgression_id, 0) + 1
                if elem.role not in definition.applies_to:
                    violations.append(f"Transgression '{transgression_id}' does not apply to role '{elem.role}'.")
                if counts[transgression_id] > definition.max_per_page:
                    violations.append(f"Transgression '{transgression_id}' exceeds max_per_page={definition.max_per_page}.")
        return violations

    def is_within_budget(self, scene_graph: SceneGraph) -> Tuple[bool, float, float]:
        energy, _ = self.calculate_page_energy(scene_graph)
        return (energy <= self.budget), energy, self.budget
