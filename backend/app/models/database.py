import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path
from ..config import settings
from .schemas import (
    Project, TitleDNA, CorpusPage, GenerationRun,
    Candidate, PreferenceSignal, TasteModel, ExportArtifact
)

class Database:
    def __init__(self, db_path: Path = settings.db_path):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'ready',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS title_dna (
                project_id TEXT PRIMARY KEY,
                dna_json TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS corpus_pages (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                extracted_features_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """)

            # Global reference pages are indexed in place: only numerical
            # features and source paths are stored, never copies of the assets.
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_corpus_indexes (
                root TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                indexed_at TEXT NOT NULL
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_corpus_pages (
                root TEXT NOT NULL,
                file_path TEXT NOT NULL,
                title_id TEXT NOT NULL,
                category TEXT NOT NULL,
                archetype_id TEXT NOT NULL,
                zone TEXT NOT NULL,
                features_json TEXT NOT NULL,
                PRIMARY KEY (root, file_path),
                FOREIGN KEY (root) REFERENCES global_corpus_indexes(root) ON DELETE CASCADE
            );
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS global_corpus_page_style_idx
                ON global_corpus_pages(root, archetype_id, zone);
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS style_archetypes (
                root TEXT NOT NULL,
                archetype_id TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                PRIMARY KEY (root, archetype_id),
                FOREIGN KEY (root) REFERENCES global_corpus_indexes(root) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS generation_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                material_json TEXT NOT NULL,
                status TEXT DEFAULT 'completed',
                stats_json TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                scene_graph_json TEXT NOT NULL,
                critic_json TEXT NOT NULL,
                svg_thumbnail TEXT,
                rank INTEGER DEFAULT 0,
                selected INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES generation_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS preference_signals (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                winner_candidate_id TEXT NOT NULL,
                loser_candidate_id TEXT,
                delta_features_json TEXT,
                timestamp TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS taste_models (
                project_id TEXT PRIMARY KEY,
                version INTEGER DEFAULT 1,
                feature_weights_json TEXT NOT NULL,
                sample_count INTEGER DEFAULT 0,
                human_preference_win_rate REAL DEFAULT 0.0,
                time_to_approve_avg_iterations REAL DEFAULT 0.0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS export_artifacts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                format TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS editorial_objects (
                id TEXT PRIMARY KEY,
                object_type TEXT NOT NULL,
                project_id TEXT,
                issue_ref TEXT,
                version INTEGER NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS editorial_revisions (
                revision_id TEXT PRIMARY KEY,
                object_id TEXT NOT NULL,
                object_type TEXT NOT NULL,
                version INTEGER NOT NULL,
                parent_revision_id TEXT,
                payload_json TEXT NOT NULL,
                author_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (object_id) REFERENCES editorial_objects(id) ON DELETE CASCADE
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS editorial_events (
                id TEXT PRIMARY KEY,
                object_id TEXT,
                event_type TEXT NOT NULL,
                reason TEXT,
                actor_id TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            );
            """)
            conn.commit()

    # --- Project Operations ---
    def create_project(self, project: Project) -> Project:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO projects (id, name, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    status = excluded.status,
                    updated_at = excluded.updated_at
            """, (project.id, project.name, project.description, project.status, project.created_at, project.updated_at))
            conn.commit()
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Project(**dict(row))

    def list_projects(self) -> List[Project]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
            return [Project(**dict(row)) for row in cursor.fetchall()]

    def delete_project(self, project_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            issue_rows = cursor.execute("SELECT id FROM editorial_objects WHERE object_type = 'issue' AND project_id = ?", (project_id,)).fetchall()
            issue_ids = [row["id"] for row in issue_rows]
            if issue_ids:
                placeholders = ",".join("?" for _ in issue_ids)
                cursor.execute(f"DELETE FROM editorial_objects WHERE project_id = ? OR issue_ref IN ({placeholders})", [project_id, *issue_ids])
            else:
                cursor.execute("DELETE FROM editorial_objects WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --- Title DNA Operations ---
    def save_title_dna(self, project_id: str, dna: TitleDNA) -> TitleDNA:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO title_dna (project_id, dna_json, version, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(project_id) DO UPDATE SET
                    dna_json = excluded.dna_json,
                    version = version + 1,
                    updated_at = excluded.updated_at
            """, (project_id, dna.model_dump_json(), dna.version))
            conn.commit()
        return dna

    def get_title_dna(self, project_id: str) -> Optional[TitleDNA]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT dna_json FROM title_dna WHERE project_id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = json.loads(row["dna_json"])
            return TitleDNA(**data)

    # --- Corpus Page Operations ---
    def add_corpus_page(self, page: CorpusPage) -> CorpusPage:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO corpus_pages (id, project_id, title, file_path, file_type, extracted_features_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    file_path = excluded.file_path,
                    extracted_features_json = excluded.extracted_features_json
            """, (page.id, page.project_id, page.title, page.file_path, page.file_type, json.dumps(page.extracted_features), page.created_at))
            conn.commit()
        return page

    def list_corpus_pages(self, project_id: str) -> List[CorpusPage]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM corpus_pages WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
            pages = []
            for row in cursor.fetchall():
                d = dict(row)
                d["extracted_features"] = json.loads(d.pop("extracted_features_json") or "{}")
                pages.append(CorpusPage(**d))
            return pages

    def get_corpus_page(self, project_id: str, page_id: str) -> Optional[CorpusPage]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM corpus_pages WHERE project_id = ? AND id = ?", (project_id, page_id)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["extracted_features"] = json.loads(data.pop("extracted_features_json") or "{}")
            return CorpusPage(**data)

    def delete_corpus_page(self, project_id: str, page_id: str) -> bool:
        with self.get_connection() as conn:
            row = conn.execute("SELECT file_path FROM corpus_pages WHERE project_id = ? AND id = ?", (project_id, page_id)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM corpus_pages WHERE project_id = ? AND id = ?", (project_id, page_id))
            conn.commit()
            return True

    # --- Global Corpus Reference Operations ---
    def save_global_corpus_index(self, index: Dict[str, Any]) -> Dict[str, Any]:
        """Atomically replace a measured global index and its five profiles.

        Only metadata and feature JSON are written.  Source files remain in
        place and are not copied or modified by this operation.
        """
        if not isinstance(index, dict) or not index.get("root"):
            raise ValueError("Global corpus index requires a root directory")
        pages = index.get("pages", [])
        profiles = index.get("archetypes", {})
        if not isinstance(pages, list) or not isinstance(profiles, dict):
            raise ValueError("Global corpus index pages/profiles have invalid types")
        root = str(Path(index["root"]).expanduser().resolve())
        indexed_at = datetime.now(timezone.utc).isoformat()
        metadata = {key: value for key, value in index.items() if key not in {"pages", "archetypes"}}
        metadata.update({"root": root, "page_count": len(pages), "indexed": True, "indexed_at": indexed_at})
        rows = []
        for page in pages:
            if not isinstance(page, dict) or not page.get("path"):
                raise ValueError("Each global corpus page requires a source path")
            source_path = str(Path(page["path"]).expanduser().resolve())
            features = dict(page)
            features["path"] = source_path
            rows.append((root, source_path, str(page.get("title_id") or ""), str(page.get("category") or ""), str(page.get("archetype_id") or page.get("archetype") or ""), str(page.get("zone") or page.get("page_zone") or "inside"), json.dumps(features, ensure_ascii=False)))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO global_corpus_indexes(root, version, metadata_json, indexed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(root) DO UPDATE SET version=excluded.version,
                    metadata_json=excluded.metadata_json, indexed_at=excluded.indexed_at
            """, (root, str(index.get("version") or "2.0.0"), json.dumps(metadata, ensure_ascii=False), indexed_at))
            cursor.execute("DELETE FROM global_corpus_pages WHERE root = ?", (root,))
            cursor.execute("DELETE FROM style_archetypes WHERE root = ?", (root,))
            cursor.executemany("""
                INSERT INTO global_corpus_pages(root, file_path, title_id, category, archetype_id, zone, features_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, rows)
            cursor.executemany("""
                INSERT INTO style_archetypes(root, archetype_id, profile_json) VALUES (?, ?, ?)
            """, [(root, str(key), json.dumps(value, ensure_ascii=False)) for key, value in profiles.items()])
            conn.commit()
        return self.get_global_corpus_index(root) or metadata

    def _global_corpus_root(self, conn: sqlite3.Connection, root: Optional[str] = None) -> Optional[str]:
        if root is not None:
            normalized = str(Path(root).expanduser().resolve())
            row = conn.execute("SELECT root FROM global_corpus_indexes WHERE root = ?", (normalized,)).fetchone()
        else:
            row = conn.execute("SELECT root FROM global_corpus_indexes ORDER BY indexed_at DESC LIMIT 1").fetchone()
        return str(row["root"]) if row else None

    def get_global_corpus_index(self, root: Optional[str] = None, *, include_pages: bool = True) -> Optional[Dict[str, Any]]:
        """Read a saved global index, selecting the most recent root by default."""
        with self.get_connection() as conn:
            selected_root = self._global_corpus_root(conn, root)
            if not selected_root:
                return None
            row = conn.execute("SELECT metadata_json FROM global_corpus_indexes WHERE root = ?", (selected_root,)).fetchone()
            index = json.loads(row["metadata_json"])
            profiles = conn.execute("SELECT archetype_id, profile_json FROM style_archetypes WHERE root = ? ORDER BY archetype_id", (selected_root,)).fetchall()
            index["archetypes"] = {profile["archetype_id"]: json.loads(profile["profile_json"]) for profile in profiles}
            if include_pages:
                pages = conn.execute("SELECT features_json FROM global_corpus_pages WHERE root = ? ORDER BY category, title_id, zone, file_path", (selected_root,)).fetchall()
                index["pages"] = [json.loads(page["features_json"]) for page in pages]
            return index

    def list_global_corpus_features(self, root: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return measured pages, including novelty vectors, for the critic."""
        index = self.get_global_corpus_index(root, include_pages=True)
        return index.get("pages", []) if index else []

    def get_global_archetype_profiles(self, root: Optional[str] = None) -> Dict[str, Any]:
        index = self.get_global_corpus_index(root, include_pages=False)
        return index.get("archetypes", {}) if index else {}

    # --- Editorial content, revisions and immutable events ---
    def save_editorial_object(self, object_type: str, model: Any, *, project_id: Optional[str] = None, issue_ref: Optional[str] = None, reason: str = "save") -> Dict[str, Any]:
        payload = model.model_dump(mode="json") if hasattr(model, "model_dump") else dict(model)
        object_id = str(payload["id"])
        now = str(payload.get("updated_at") or datetime.now(timezone.utc).isoformat())
        version = int(payload.get("version") or 1)
        status = str(payload.get("status") or "draft")
        parent_revision_id = payload.get("parent_revision_id")
        revision_id = f"{object_id}:v{version}"
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO editorial_objects(id, object_type, project_id, issue_ref, version, status, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET object_type=excluded.object_type,
                    project_id=excluded.project_id, issue_ref=excluded.issue_ref,
                    version=excluded.version, status=excluded.status,
                    payload_json=excluded.payload_json, updated_at=excluded.updated_at
            """, (object_id, object_type, project_id or payload.get("project_id"), issue_ref or payload.get("issue_ref"), version, status, json.dumps(payload, ensure_ascii=False), str(payload.get("created_at") or now), now))
            conn.execute("""
                INSERT OR REPLACE INTO editorial_revisions(revision_id, object_id, object_type, version, parent_revision_id, payload_json, author_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (revision_id, object_id, object_type, version, parent_revision_id, json.dumps(payload, ensure_ascii=False), payload.get("author_id"), now))
            conn.execute("""
                INSERT INTO editorial_events(id, object_id, event_type, reason, actor_id, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), object_id, "revision_saved", reason, payload.get("author_id"), json.dumps({"version": version}, ensure_ascii=False), now))
            conn.commit()
        return payload

    def get_editorial_object(self, object_type: str, object_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT payload_json FROM editorial_objects WHERE id = ? AND object_type = ?", (object_id, object_type)).fetchone()
            return json.loads(row["payload_json"]) if row else None

    def list_editorial_objects(self, object_type: str, *, issue_ref: Optional[str] = None, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT payload_json FROM editorial_objects WHERE object_type = ?"
        args: List[Any] = [object_type]
        if issue_ref:
            query += " AND issue_ref = ?"; args.append(issue_ref)
        if project_id:
            query += " AND project_id = ?"; args.append(project_id)
        query += " ORDER BY updated_at DESC"
        with self.get_connection() as conn:
            return [json.loads(row["payload_json"]) for row in conn.execute(query, args).fetchall()]

    def list_editorial_revisions(self, object_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM editorial_revisions WHERE object_id = ? ORDER BY version ASC", (object_id,)).fetchall()
            return [dict(row) | {"payload": json.loads(row["payload_json"])} for row in rows]

    def record_editorial_event(self, object_id: Optional[str], event_type: str, *, reason: Optional[str] = None, actor_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        event = {"id": str(uuid.uuid4()), "object_id": object_id, "event_type": event_type, "reason": reason, "actor_id": actor_id, "metadata": metadata or {}, "created_at": datetime.now(timezone.utc).isoformat()}
        with self.get_connection() as conn:
            conn.execute("INSERT INTO editorial_events(id, object_id, event_type, reason, actor_id, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (event["id"], object_id, event_type, reason, actor_id, json.dumps(metadata or {}, ensure_ascii=False), event["created_at"]))
            conn.commit()
        return event

    # Short aliases keep integrations that call this resource simply
    # ``corpus_index`` source-compatible with the explicit global names above.
    save_corpus_index = save_global_corpus_index
    get_corpus_index = get_global_corpus_index
    list_corpus_features = list_global_corpus_features

    # --- Generation Run & Candidates ---
    def save_generation_run(self, run: GenerationRun) -> GenerationRun:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO generation_runs (id, project_id, timestamp, material_json, status, stats_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    stats_json = excluded.stats_json
            """, (run.id, run.project_id, run.timestamp, run.material.model_dump_json(), run.status, json.dumps(run.stats)))
            for cand in run.candidates:
                cursor.execute("""
                    INSERT INTO candidates (id, run_id, project_id, scene_graph_json, critic_json, svg_thumbnail, rank, selected, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        scene_graph_json = excluded.scene_graph_json,
                        critic_json = excluded.critic_json,
                        svg_thumbnail = excluded.svg_thumbnail,
                        rank = excluded.rank,
                        selected = excluded.selected
                """, (
                    cand.id, cand.run_id, run.project_id,
                    cand.scene_graph.model_dump_json(),
                    cand.critic.model_dump_json(),
                    cand.svg_thumbnail,
                    cand.rank,
                    1 if cand.selected else 0,
                    cand.created_at
                ))
            conn.commit()
        return run

    def get_generation_run(self, run_id: str) -> Optional[GenerationRun]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM generation_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            run_dict = dict(row)
            material_data = json.loads(run_dict["material_json"])
            stats_data = json.loads(run_dict["stats_json"] or "{}")

            cursor.execute("SELECT * FROM candidates WHERE run_id = ? ORDER BY rank ASC", (run_id,))
            cand_rows = cursor.fetchall()
            candidates = []
            for c in cand_rows:
                cd = dict(c)
                cand = Candidate(
                    id=cd["id"],
                    run_id=cd["run_id"],
                    scene_graph=json.loads(cd["scene_graph_json"]),
                    critic=json.loads(cd["critic_json"]),
                    svg_thumbnail=cd["svg_thumbnail"],
                    rank=cd["rank"],
                    selected=bool(cd["selected"]),
                    created_at=cd["created_at"]
                )
                candidates.append(cand)

            return GenerationRun(
                id=run_dict["id"],
                project_id=run_dict["project_id"],
                timestamp=run_dict["timestamp"],
                material=material_data,
                status=run_dict["status"],
                candidates=candidates,
                stats=stats_data
            )

    def list_generation_runs(self, project_id: str) -> List[GenerationRun]:
        """Return a project's runs in newest-first order.

        Keep hydration in one place by reusing ``get_generation_run`` for the
        candidate graph and critic payloads.  This is intentionally a small
        query followed by deterministic hydration: the frontend needs the
        same complete run contract whether it opens one run or the history.
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT id FROM generation_runs WHERE project_id = ? ORDER BY timestamp DESC",
                (project_id,),
            ).fetchall()
        runs: List[GenerationRun] = []
        for row in rows:
            run = self.get_generation_run(row["id"])
            if run is not None:
                runs.append(run)
        return runs

    def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
            row = cursor.fetchone()
            if not row:
                return None
            cd = dict(row)
            return Candidate(
                id=cd["id"],
                run_id=cd["run_id"],
                scene_graph=json.loads(cd["scene_graph_json"]),
                critic=json.loads(cd["critic_json"]),
                svg_thumbnail=cd["svg_thumbnail"],
                rank=cd["rank"],
                selected=bool(cd["selected"]),
                created_at=cd["created_at"]
            )

    def get_candidate_project_id(self, candidate_id: str) -> Optional[str]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT project_id FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
            return row["project_id"] if row else None

    def update_candidate_scene(self, candidate_id: str, scene_graph_json: str, critic_json: str, svg_thumbnail: Optional[str] = None) -> Optional[Candidate]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE candidates SET scene_graph_json = ?, critic_json = ?, svg_thumbnail = COALESCE(?, svg_thumbnail) WHERE id = ?",
                (scene_graph_json, critic_json, svg_thumbnail, candidate_id),
            )
            conn.commit()
        return self.get_candidate(candidate_id)

    # --- Preference Signals & Taste Model ---
    def record_preference_signal(self, sig: PreferenceSignal) -> PreferenceSignal:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO preference_signals (id, project_id, signal_type, winner_candidate_id, loser_candidate_id, delta_features_json, timestamp, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sig.id, sig.project_id, sig.signal_type,
                sig.winner_candidate_id, sig.loser_candidate_id,
                json.dumps(sig.delta_features or {}),
                sig.timestamp, sig.notes
            ))
            # Mark candidate as selected if it's a selection signal
            cursor.execute("UPDATE candidates SET selected = 1 WHERE id = ?", (sig.winner_candidate_id,))
            conn.commit()
        return sig

    def list_preference_signals(self, project_id: str) -> List[PreferenceSignal]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM preference_signals WHERE project_id = ? ORDER BY timestamp ASC", (project_id,))
            signals = []
            for row in cursor.fetchall():
                d = dict(row)
                d["delta_features"] = json.loads(d.pop("delta_features_json") or "{}")
                signals.append(PreferenceSignal(**d))
            return signals

    def save_taste_model(self, model: TasteModel) -> TasteModel:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO taste_models (project_id, version, feature_weights_json, sample_count, human_preference_win_rate, time_to_approve_avg_iterations, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(project_id) DO UPDATE SET
                    version = version + 1,
                    feature_weights_json = excluded.feature_weights_json,
                    sample_count = excluded.sample_count,
                    human_preference_win_rate = excluded.human_preference_win_rate,
                    time_to_approve_avg_iterations = excluded.time_to_approve_avg_iterations,
                    updated_at = excluded.updated_at
            """, (
                model.project_id, model.version,
                json.dumps(model.feature_weights),
                model.sample_count,
                model.human_preference_win_rate,
                model.time_to_approve_avg_iterations
            ))
            conn.commit()
        return model

    def get_taste_model(self, project_id: str) -> Optional[TasteModel]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM taste_models WHERE project_id = ?", (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["feature_weights"] = json.loads(d.pop("feature_weights_json") or "{}")
            return TasteModel(**d)

    # --- Export Artifacts ---
    def save_export_artifact(self, artifact: ExportArtifact) -> ExportArtifact:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO export_artifacts (id, project_id, candidate_id, format, file_path, file_size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                artifact.id, artifact.project_id, artifact.candidate_id,
                artifact.format, artifact.file_path, artifact.file_size_bytes,
                artifact.created_at
            ))
            conn.commit()
        return artifact

    def list_export_artifacts(self, project_id: Optional[str] = None) -> List[ExportArtifact]:
        query = "SELECT * FROM export_artifacts"
        args: List[Any] = []
        if project_id:
            query += " WHERE project_id = ?"
            args.append(project_id)
        query += " ORDER BY created_at DESC"
        with self.get_connection() as conn:
            return [ExportArtifact(**dict(row)) for row in conn.execute(query, args).fetchall()]

db = Database()
