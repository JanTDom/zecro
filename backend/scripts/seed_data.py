import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.models.database import db
from backend.app.models.schemas import (
    Project, TitleDNA, CorpusPage, PageInputMaterial, StoryInput, StoryImageInput,
    GenerationRequest, PreferenceSignal
)
from backend.app.engine.grammar import create_default_broadsheet_dna, create_default_tabloid_dna
from backend.app.api.generate import execute_generation_run
from backend.app.api.preferences import record_preference

def seed():
    print("🌱 Seeding Layout Studio Database with Initial Editorial Projects...")

    # 1. Project 1: The Daily Chronicle (Broadsheet)
    p1 = Project(
        id="proj-daily-chronicle",
        name="The Daily Chronicle",
        description="Prestigious broadsheet newspaper with classical typography, disciplined 6-column modular grid, and refined visual hierarchy.",
        status="ready"
    )
    db.create_project(p1)
    dna1 = create_default_broadsheet_dna()
    dna1.name = "The Daily Chronicle DNA"
    db.save_title_dna(p1.id, dna1)

    # Add Corpus Pages for Project 1
    c1 = CorpusPage(
        id="corpus-chronicle-01",
        project_id=p1.id,
        title="Chronicle Issue 14,800 - Lead Front Page",
        file_path="corpus_chronicle_01.pdf",
        file_type="pdf",
        extracted_features={
            "vector": [0.04, 0.09, 0.92, 0.11, 0.04, 0.20, 0.48, 0.32, 0.0, 0.40],
            "dominant_columns": 6,
            "headline_scale_ratio": 5.2,
            "photo_coverage_pct": 24.0,
            "avg_transgressions_per_page": 0.5
        }
    )
    c2 = CorpusPage(
        id="corpus-chronicle-02",
        project_id=p1.id,
        title="Chronicle Issue 14,801 - Investigative Feature",
        file_path="corpus_chronicle_02.pdf",
        file_type="pdf",
        extracted_features={
            "vector": [0.04, 0.09, 0.60, 0.14, 0.65, 0.10, 0.30, 0.40, 1.0, 0.70],
            "dominant_columns": 6,
            "headline_scale_ratio": 4.6,
            "photo_coverage_pct": 30.0,
            "avg_transgressions_per_page": 0.8
        }
    )
    db.add_corpus_page(c1)
    db.add_corpus_page(c2)

    # 2. Project 2: Gazeta Codzienna (Expressive Tabloid)
    p2 = Project(
        id="proj-gazeta-codzienna",
        name="Gazeta Codzienna",
        description="High-energy urban tabloid with bold sans-serif kickers, dramatic photo cutouts, contour text wrap, and dynamic diagonals.",
        status="ready"
    )
    db.create_project(p2)
    dna2 = create_default_tabloid_dna()
    dna2.name = "Gazeta Codzienna DNA"
    db.save_title_dna(p2.id, dna2)

    c3 = CorpusPage(
        id="corpus-gazeta-01",
        project_id=p2.id,
        title="Wydanie Specjalne - Rewolucja w Mieście",
        file_path="corpus_gazeta_01.jpg",
        file_type="image",
        extracted_features={
            "vector": [0.03, 0.12, 0.94, 0.18, 0.10, 0.30, 0.55, 0.42, 1.0, 1.10],
            "dominant_columns": 5,
            "headline_scale_ratio": 7.0,
            "photo_coverage_pct": 38.0,
            "avg_transgressions_per_page": 1.4
        }
    )
    db.add_corpus_page(c3)

    # 3. Generate Initial Layout Run for The Daily Chronicle
    print("📰 Executing Initial Evolutionary Generation Run for The Daily Chronicle...")
    material1 = PageInputMaterial(
        issue_date="Tuesday, September 1, 2026",
        issue_number="Vol. CLXXV No. 58,912",
        section_name="GLOBAL AFFAIRS & ARCHITECTURE",
        masthead_title="THE DAILY CHRONICLE",
        stories=[
            StoryInput(
                id="story-architects",
                kicker="SUMMIT ON THE FUTURE OF CITIES",
                headline="GLOBAL SUMMIT MAPS NEW ARCHITECTURAL BLUEPRINTS FOR AUTONOMOUS MEGACITIES",
                deck="Leading urban planners and computational designers unveil sustainable metropolitan frameworks balancing dense modular infrastructure with generous green commons.",
                byline="BY ELEANOR VANCE IN ROTTERDAM",
                lead="Metropolitan planning entered a transformative era today as international architects ratified the 2030 Spatial Harmony Accord. The framework mandates dynamic modular zoning, self-healing transit corridors, and algorithmic light distribution.",
                body="Addressing thousands of delegates at the Metropolis Centre, Chief Architect Helena Rostova emphasized that structural elegance cannot be achieved through uniformity alone.\n\n\"The city is not a static grid of steel and concrete, but a breathing typographical landscape,\" Rostova stated during her keynote address. \"Just as an editorial page demands baseline discipline paired with purposeful artistic accents, sustainable urban hubs require both rigorous modular efficiency and organic public breathing rooms.\"\n\nDelegations from over forty nations pledged immediate funding for carbon-negative timber high-rises and integrated subterranean logistics networks.",
                importance=1.0,
                images=[
                    StoryImageInput(
                        id="img-tower",
                        url="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&q=80",
                        caption="The new Solaris Spire in Rotterdam incorporates dynamic timber terraces.",
                        credit="Photo: Marcus Lindqvist / Reuters",
                        importance=0.9,
                        is_cutout_candidate=True
                    )
                ]
            ),
            StoryInput(
                id="story-markets",
                kicker="FINANCIAL BULLETIN",
                headline="MARKETS RALLY ON BREAKTHROUGH CLEAN ENERGY TREATY",
                byline="BY DAVID K. STERN",
                lead="Equities across European and Asian bourses surged to five-year highs as industrial leaders finalized cross-border power agreements.",
                body="Trading desks reported record volume in solar grid operators and next-generation battery fabricators. The pan-European index gained 2.4 percent in morning trade.",
                importance=0.6
            )
        ]
    )

    req = GenerationRequest(
        material=material1,
        num_candidates=6,
        population_size=15,
        generations=6
    )

    run = execute_generation_run(p1.id, req)
    print(f"✅ Generated {len(run.candidates)} candidates for run {run.id}. Top candidate fitness: {run.candidates[0].critic.total_fitness}")

    # 4. Record a sample Pairwise Preference Signal
    if len(run.candidates) >= 2:
        sig = PreferenceSignal(
            project_id=p1.id,
            signal_type="pairwise_comparison",
            winner_candidate_id=run.candidates[0].id,
            loser_candidate_id=run.candidates[1].id,
            notes="Art director preferred candidate with dominant vertical photo cutout and balanced lead paragraph."
        )
        record_preference(p1.id, sig)
        print("⭐️ Recorded baseline preference signal and initialized project Taste Model.")

    print("\n🎉 Seeding completed successfully!")

if __name__ == "__main__":
    seed()
