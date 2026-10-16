"""SQLite persistence for local workflow definitions and execution records."""

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


class BootstrapClosed(Exception):
    """Initial local owner account has already been created."""


class WorkflowStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 80),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memberships (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('owner', 'member')),
                    PRIMARY KEY(user_id, workspace_id)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    csrf_token TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_versions (
                    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                    version INTEGER NOT NULL CHECK(version > 0),
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(agent_id, version)
                );
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                    name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 80),
                    current_version INTEGER NOT NULL CHECK(current_version > 0),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    archived_at TEXT
                );
                CREATE INDEX IF NOT EXISTS agents_workspace_updated
                    ON agents(workspace_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 80),
                    definition_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    workspace_id TEXT REFERENCES workspaces(id)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS runs_workflow_created
                    ON runs(workflow_id, created_at DESC);
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(workflows)")}
            if "workspace_id" not in columns:
                connection.execute("ALTER TABLE workflows ADD COLUMN workspace_id TEXT")
            if connection.execute("SELECT 1 FROM workflows LIMIT 1").fetchone():
                connection.execute(
                    "INSERT OR IGNORE INTO workspaces (id, name, created_at) VALUES (?, ?, ?)",
                    ("legacy-local-workspace", "Local workspace", _now()),
                )
                connection.execute(
                    "UPDATE workflows SET workspace_id = ? WHERE workspace_id IS NULL",
                    ("legacy-local-workspace",),
                )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def bootstrap_owner(
        self, email: str, password_hash: str, workspace_name: str
    ) -> dict[str, str]:
        user = {"id": uuid.uuid4().hex, "email": email, "created_at": _now()}
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise BootstrapClosed("initial account already exists")
            legacy = connection.execute(
                "SELECT id FROM workspaces WHERE id = ?", ("legacy-local-workspace",)
            ).fetchone()
            workspace_id = legacy["id"] if legacy else uuid.uuid4().hex
            if legacy:
                connection.execute(
                    "UPDATE workspaces SET name = ? WHERE id = ?",
                    (workspace_name, workspace_id),
                )
            else:
                connection.execute(
                    "INSERT INTO workspaces (id, name, created_at) VALUES (?, ?, ?)",
                    (workspace_id, workspace_name, _now()),
                )
            connection.execute(
                "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user["id"], email, password_hash, user["created_at"]),
            )
            connection.execute(
                "INSERT INTO memberships (user_id, workspace_id, role) VALUES (?, ?, 'owner')",
                (user["id"], workspace_id),
            )
            connection.execute(
                "UPDATE workflows SET workspace_id = ? "
                "WHERE workspace_id IS NULL OR workspace_id = ?",
                (workspace_id, "legacy-local-workspace"),
            )
        return {
            **user,
            "workspace_id": workspace_id,
            "workspace_name": workspace_name,
            "role": "owner",
        }

    def user_count(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def get_user(self, email: str) -> dict[str, str] | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT u.id, u.email, u.password_hash, m.workspace_id,
                          w.name AS workspace_name, m.role
                   FROM users u JOIN memberships m ON m.user_id = u.id
                   JOIN workspaces w ON w.id = m.workspace_id WHERE u.email = ? COLLATE NOCASE""",
                (email,),
            ).fetchone()
        return dict(row) if row else None

    def create_session(
        self, token_hash: str, csrf_token: str, user_id: str, expires_at: str
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, csrf_token, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (token_hash, user_id, csrf_token, expires_at, _now()),
            )

    def get_session(self, token_hash: str) -> dict[str, str] | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT u.id, u.email, m.workspace_id, w.name AS workspace_name, m.role,
                          s.csrf_token, s.expires_at
                   FROM sessions s JOIN users u ON u.id = s.user_id
                   JOIN memberships m ON m.user_id = u.id
                   JOIN workspaces w ON w.id = m.workspace_id
                   WHERE s.token_hash = ? AND s.expires_at > ?""",
                (token_hash, _now()),
            ).fetchone()
        return dict(row) if row else None

    def revoke_session(self, token_hash: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    @staticmethod
    def _agent_from_row(row: sqlite3.Row, config_json: str | None = None) -> dict[str, Any]:
        config_json = row["config_json"] if config_json is None else config_json
        return {
            "id": row["id"],
            "workspace_id": row["workspace_id"],
            "name": row["name"],
            "version": row["current_version"],
            "config": json.loads(config_json),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_agent(self, config: dict[str, Any], workspace_id: str) -> dict[str, Any]:
        agent_id = uuid.uuid4().hex
        now = _now()
        config_json = json.dumps(config, allow_nan=False)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO agents "
                "(id, workspace_id, name, current_version, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                (agent_id, workspace_id, config["name"], now, now),
            )
            connection.execute(
                "INSERT INTO agent_versions (agent_id, version, config_json, created_at) "
                "VALUES (?, 1, ?, ?)",
                (agent_id, config_json, now),
            )
            row = connection.execute(
                "SELECT a.*, v.config_json FROM agents a JOIN agent_versions v "
                "ON v.agent_id = a.id AND v.version = a.current_version WHERE a.id = ?",
                (agent_id,),
            ).fetchone()
        return self._agent_from_row(row)

    def get_agent(self, agent_id: str, workspace_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT a.*, v.config_json FROM agents a JOIN agent_versions v "
                "ON v.agent_id = a.id AND v.version = a.current_version "
                "WHERE a.id = ? AND a.workspace_id = ? AND a.archived_at IS NULL",
                (agent_id, workspace_id),
            ).fetchone()
        return self._agent_from_row(row) if row else None

    def list_agents(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT a.*, v.config_json FROM agents a JOIN agent_versions v "
                "ON v.agent_id = a.id AND v.version = a.current_version "
                "WHERE a.workspace_id = ? AND a.archived_at IS NULL "
                "ORDER BY a.updated_at DESC, a.id",
                (workspace_id,),
            ).fetchall()
        return [self._agent_from_row(row) for row in rows]

    def update_agent(
        self, agent_id: str, config: dict[str, Any], workspace_id: str
    ) -> dict[str, Any] | None:
        now = _now()
        config_json = json.dumps(config, allow_nan=False)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT current_version FROM agents WHERE id = ? AND workspace_id = ? "
                "AND archived_at IS NULL",
                (agent_id, workspace_id),
            ).fetchone()
            if row is None:
                return None
            version = int(row["current_version"]) + 1
            connection.execute(
                "INSERT INTO agent_versions (agent_id, version, config_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (agent_id, version, config_json, now),
            )
            connection.execute(
                "UPDATE agents SET name = ?, current_version = ?, updated_at = ? "
                "WHERE id = ? AND workspace_id = ?",
                (config["name"], version, now, agent_id, workspace_id),
            )
            updated = connection.execute(
                "SELECT a.*, v.config_json FROM agents a JOIN agent_versions v "
                "ON v.agent_id = a.id AND v.version = a.current_version WHERE a.id = ?",
                (agent_id,),
            ).fetchone()
        return self._agent_from_row(updated)

    def list_agent_versions(self, agent_id: str, workspace_id: str) -> list[dict[str, Any]] | None:
        with self._connection() as connection:
            allowed = connection.execute(
                "SELECT 1 FROM agents WHERE id = ? AND workspace_id = ?",
                (agent_id, workspace_id),
            ).fetchone()
            if not allowed:
                return None
            rows = connection.execute(
                "SELECT v.version, v.config_json, v.created_at FROM agent_versions v "
                "JOIN agents a ON a.id = v.agent_id WHERE v.agent_id = ? "
                "AND a.workspace_id = ? ORDER BY v.version DESC",
                (agent_id, workspace_id),
            ).fetchall()
        return [
            {
                "version": row["version"],
                "config": json.loads(row["config_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def archive_agent(self, agent_id: str, workspace_id: str) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE agents SET archived_at = ? WHERE id = ? AND workspace_id = ? "
                "AND archived_at IS NULL",
                (_now(), agent_id, workspace_id),
            )
        return cursor.rowcount > 0

    def create_workflow(
        self, name: str, definition: dict[str, Any], workspace_id: str
    ) -> dict[str, Any]:
        workflow = {
            "id": uuid.uuid4().hex,
            "name": name,
            "definition": definition,
            "created_at": _now(),
            "workspace_id": workspace_id,
        }
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO workflows "
                "(id, name, definition_json, created_at, workspace_id) VALUES (?, ?, ?, ?, ?)",
                (
                    workflow["id"],
                    name,
                    json.dumps(definition, allow_nan=False),
                    workflow["created_at"],
                    workspace_id,
                ),
            )
        return workflow

    @staticmethod
    def _workflow_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "definition": json.loads(row["definition_json"]),
            "created_at": row["created_at"],
            "workspace_id": row["workspace_id"],
        }

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "workflow_id": row["workflow_id"],
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }

    def update_workflow(
        self, workflow_id: str, name: str, definition: dict[str, Any], workspace_id: str
    ) -> dict[str, Any] | None:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE workflows SET name = ?, definition_json = ? "
                "WHERE id = ? AND workspace_id = ?",
                (
                    name,
                    json.dumps(definition, allow_nan=False),
                    workflow_id,
                    workspace_id,
                ),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
        return self._workflow_from_row(row)

    def list_workflows(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM workflows WHERE workspace_id = ? ORDER BY created_at DESC, id",
                (workspace_id,),
            ).fetchall()
        return [self._workflow_from_row(row) for row in rows]

    def get_workflow(self, workflow_id: str, workspace_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM workflows WHERE id = ? AND workspace_id = ?",
                (workflow_id, workspace_id),
            ).fetchone()
        return self._workflow_from_row(row) if row else None

    def create_run(
        self, workflow_id: str, result: dict[str, Any], workspace_id: str
    ) -> dict[str, Any]:
        run = {
            "id": uuid.uuid4().hex,
            "workflow_id": workflow_id,
            "result": result,
            "created_at": _now(),
        }
        with self._connection() as connection:
            allowed = connection.execute(
                "SELECT 1 FROM workflows WHERE id = ? AND workspace_id = ?",
                (workflow_id, workspace_id),
            ).fetchone()
            if not allowed:
                raise LookupError("workflow not found")
            connection.execute(
                "INSERT INTO runs (id, workflow_id, result_json, created_at) VALUES (?, ?, ?, ?)",
                (
                    run["id"],
                    workflow_id,
                    json.dumps(result, allow_nan=False),
                    run["created_at"],
                ),
            )
        return run

    def list_runs(self, workflow_id: str, workspace_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT r.* FROM runs r JOIN workflows w ON w.id = r.workflow_id
                   WHERE r.workflow_id = ? AND w.workspace_id = ?
                   ORDER BY r.created_at DESC, r.id""",
                (workflow_id, workspace_id),
            ).fetchall()
        return [self._run_from_row(row) for row in rows]
