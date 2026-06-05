import json
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from plugins.memory.openviking import (
    OpenVikingMemoryProvider,
    OpenVikingPermanentError,
    OpenVikingTransientError,
    _VikingClient,
)


def test_tool_search_sorts_by_raw_score_across_buckets():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.post.return_value = {
        "result": {
            "memories": [
                {"uri": "viking://memories/1", "score": 0.9003, "abstract": "memory result"},
            ],
            "resources": [
                {"uri": "viking://resources/1", "score": 0.9004, "abstract": "resource result"},
            ],
            "skills": [
                {"uri": "viking://skills/1", "score": 0.8999, "abstract": "skill result"},
            ],
            "total": 3,
        }
    }

    result = json.loads(provider._tool_search({"query": "ranking"}))

    assert [entry["uri"] for entry in result["results"]] == [
        "viking://resources/1",
        "viking://memories/1",
        "viking://skills/1",
    ]
    assert [entry["score"] for entry in result["results"]] == [0.9, 0.9, 0.9]
    assert result["total"] == 3


def test_tool_search_sorts_missing_raw_score_after_negative_scores():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.post.return_value = {
        "result": {
            "memories": [
                {"uri": "viking://memories/missing", "abstract": "missing score"},
            ],
            "resources": [
                {"uri": "viking://resources/negative", "score": -0.25, "abstract": "negative score"},
            ],
            "skills": [
                {"uri": "viking://skills/positive", "score": 0.1, "abstract": "positive score"},
            ],
            "total": 3,
        }
    }

    result = json.loads(provider._tool_search({"query": "ranking"}))

    assert [entry["uri"] for entry in result["results"]] == [
        "viking://skills/positive",
        "viking://memories/missing",
        "viking://resources/negative",
    ]
    assert [entry["score"] for entry in result["results"]] == [0.1, 0.0, -0.25]
    assert result["total"] == 3


def test_tool_add_resource_uploads_existing_local_file(tmp_path):
    sample = tmp_path / "sample.md"
    sample.write_text("# Local resource\n", encoding="utf-8")
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.upload_temp_file.return_value = "upload_sample.md"
    provider._client.post.return_value = {
        "status": "ok",
        "result": {"root_uri": "viking://resources/sample"},
    }

    result = json.loads(provider._tool_add_resource({
        "url": str(sample),
        "reason": "local test",
        "wait": True,
    }))

    provider._client.upload_temp_file.assert_called_once_with(sample)
    provider._client.post.assert_called_once_with("/api/v1/resources", {
        "reason": "local test",
        "wait": True,
        "source_name": "sample.md",
        "temp_file_id": "upload_sample.md",
    })
    assert result["status"] == "added"
    assert result["root_uri"] == "viking://resources/sample"


def test_tool_add_resource_uploads_file_uri(tmp_path):
    sample = tmp_path / "sample.md"
    sample.write_text("# Local resource\n", encoding="utf-8")
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.upload_temp_file.return_value = "upload_sample.md"
    provider._client.post.return_value = {
        "status": "ok",
        "result": {"root_uri": "viking://resources/sample"},
    }

    result = json.loads(provider._tool_add_resource({
        "url": sample.as_uri(),
        "reason": "file uri test",
    }))

    provider._client.upload_temp_file.assert_called_once_with(sample)
    provider._client.post.assert_called_once_with("/api/v1/resources", {
        "reason": "file uri test",
        "source_name": "sample.md",
        "temp_file_id": "upload_sample.md",
    })
    assert result["status"] == "added"
    assert result["root_uri"] == "viking://resources/sample"


def test_tool_add_resource_uploads_existing_local_directory_and_cleans_zip(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n", encoding="utf-8")
    nested = docs / "nested"
    nested.mkdir()
    (nested / "api.md").write_text("# API\n", encoding="utf-8")
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    uploaded_paths = []
    provider._client.upload_temp_file.side_effect = (
        lambda path: uploaded_paths.append(path) or "upload_docs.zip"
    )
    provider._client.post.return_value = {
        "status": "ok",
        "result": {"root_uri": "viking://resources/docs"},
    }

    result = json.loads(provider._tool_add_resource({
        "url": str(docs),
        "reason": "directory test",
        "wait": True,
    }))

    assert uploaded_paths
    assert uploaded_paths[0].suffix == ".zip"
    assert not uploaded_paths[0].exists()
    provider._client.post.assert_called_once_with("/api/v1/resources", {
        "reason": "directory test",
        "wait": True,
        "source_name": "docs",
        "temp_file_id": "upload_docs.zip",
    })
    assert result["status"] == "added"
    assert result["root_uri"] == "viking://resources/docs"


def test_tool_add_resource_directory_zip_skips_symlink_escape(tmp_path):
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("do not upload\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n", encoding="utf-8")
    link = docs / "leak.txt"
    try:
        link.symlink_to(secret)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable in test environment: {exc}")

    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    archive_entries = {}

    def inspect_upload(path):
        with zipfile.ZipFile(path) as archive:
            archive_entries["names"] = archive.namelist()
            archive_entries["payloads"] = {
                name: archive.read(name)
                for name in archive.namelist()
            }
        return "upload_docs.zip"

    provider._client.upload_temp_file.side_effect = inspect_upload
    provider._client.post.return_value = {
        "status": "ok",
        "result": {"root_uri": "viking://resources/docs"},
    }

    json.loads(provider._tool_add_resource({"url": str(docs)}))

    assert archive_entries["names"] == ["guide.md"]
    assert b"do not upload" not in b"".join(archive_entries["payloads"].values())


def test_tool_add_resource_cleans_local_directory_zip_when_add_fails(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n", encoding="utf-8")
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    uploaded_paths = []
    provider._client.upload_temp_file.side_effect = (
        lambda path: uploaded_paths.append(path) or "upload_docs.zip"
    )
    provider._client.post.side_effect = RuntimeError("add failed")

    with pytest.raises(RuntimeError, match="add failed"):
        provider._tool_add_resource({"url": str(docs)})

    assert uploaded_paths
    assert not uploaded_paths[0].exists()


def test_tool_add_resource_cleans_local_directory_zip_when_upload_fails(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n", encoding="utf-8")
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    uploaded_paths = []

    def fail_upload(path):
        uploaded_paths.append(path)
        raise RuntimeError("upload failed")

    provider._client.upload_temp_file.side_effect = fail_upload

    with pytest.raises(RuntimeError, match="upload failed"):
        provider._tool_add_resource({"url": str(docs)})

    assert uploaded_paths
    assert not uploaded_paths[0].exists()
    provider._client.post.assert_not_called()


def test_tool_add_resource_rejects_missing_local_path(tmp_path):
    missing = tmp_path / "missing.md"
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()

    result = json.loads(provider._tool_add_resource({"url": str(missing)}))

    assert result["error"] == f"Local resource path does not exist: {missing}"
    provider._client.upload_temp_file.assert_not_called()
    provider._client.post.assert_not_called()


def test_tool_add_resource_sends_remote_url_as_path():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.post.return_value = {
        "status": "ok",
        "result": {"root_uri": "viking://resources/remote"},
    }

    provider._tool_add_resource({"url": "https://example.com/doc.md"})

    provider._client.upload_temp_file.assert_not_called()
    provider._client.post.assert_called_once_with("/api/v1/resources", {
        "path": "https://example.com/doc.md",
    })


@pytest.mark.parametrize("url", [
    "git@github.com:org/repo.git",
    "git@ssh.dev.azure.com:v3/org/project/repo",
    "ssh://git@github.com/org/repo.git",
    "git://github.com/org/repo.git",
])
def test_tool_add_resource_sends_git_remote_sources_as_path(url):
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.post.return_value = {
        "status": "ok",
        "result": {"root_uri": "viking://resources/repo"},
    }

    provider._tool_add_resource({"url": url})

    provider._client.upload_temp_file.assert_not_called()
    provider._client.post.assert_called_once_with("/api/v1/resources", {
        "path": url,
    })


def test_viking_client_upload_temp_file_uses_multipart_identity_headers(tmp_path, monkeypatch):
    sample = tmp_path / "sample.md"
    sample.write_text("# Local resource\n", encoding="utf-8")
    client = _VikingClient(
        "https://example.com",
        api_key="test-key",
        account="test-account",
        user="test-user",
        agent="test-agent",
    )
    captured_kwargs = {}

    def capture_httpx_post(url, **kwargs):
        captured_kwargs.update(kwargs)
        return SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {"status": "ok", "result": {"temp_file_id": "upload_sample.md"}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(client._httpx, "post", capture_httpx_post)

    assert client.upload_temp_file(sample) == "upload_sample.md"

    assert "files" in captured_kwargs
    assert "json" not in captured_kwargs
    headers = captured_kwargs["headers"]
    assert headers["X-OpenViking-Account"] == "test-account"
    assert headers["X-OpenViking-User"] == "test-user"
    assert headers["X-OpenViking-Agent"] == "test-agent"
    assert headers["X-API-Key"] == "test-key"
    assert "Content-Type" not in headers


def test_viking_client_raises_structured_server_error():
    client = _VikingClient.__new__(_VikingClient)
    response = SimpleNamespace(
        status_code=403,
        text='{"status":"error"}',
        json=lambda: {
            "status": "error",
            "error": {
                "code": "PERMISSION_DENIED",
                "message": "direct host filesystem paths are not allowed",
            },
        },
        raise_for_status=lambda: None,
    )

    with pytest.raises(OpenVikingPermanentError, match="PERMISSION_DENIED"):
        client._parse_response(response)


def test_viking_client_raises_transient_error_on_5xx():
    """5xx responses raise OpenVikingTransientError for retry."""
    client = _VikingClient.__new__(_VikingClient)
    response = SimpleNamespace(
        status_code=503,
        text="Service Unavailable",
        json=lambda: {"status": "error", "error": {"code": "SERVER_ERROR", "message": "busy"}},
        raise_for_status=lambda: None,
    )

    with pytest.raises(OpenVikingTransientError, match="SERVER_ERROR"):
        client._parse_response(response)


def test_viking_client_raises_permanent_error_on_4xx():
    """4xx responses raise OpenVikingPermanentError (no retry)."""
    client = _VikingClient.__new__(_VikingClient)
    response = SimpleNamespace(
        status_code=400,
        text="Bad Request",
        json=lambda: {"status": "error", "error": {"code": "BAD_REQUEST", "message": "invalid"}},
        raise_for_status=lambda: None,
    )

    with pytest.raises(OpenVikingPermanentError, match="BAD_REQUEST"):
        client._parse_response(response)


def test_viking_client_get_retries_on_transient_error(monkeypatch):
    """GET retries on transient (5xx) errors and succeeds on retry."""
    client = _VikingClient("https://example.com")
    call_count = [0]

    def failing_get(url, **kwargs):
        call_count[0] += 1
        if call_count[0] < 3:
            return SimpleNamespace(
                status_code=503,
                text="unavailable",
                json=lambda: {"status": "error", "error": {"code": "BUSY", "message": "retry"}},
                raise_for_status=lambda: None,
            )
        return SimpleNamespace(
            status_code=200,
            text="ok",
            json=lambda: {"result": {"data": "success"}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(client._httpx, "get", failing_get)

    result = client.get("/api/v1/test")
    assert result == {"result": {"data": "success"}}
    assert call_count[0] == 3


def test_viking_client_get_does_not_retry_on_permanent_error(monkeypatch):
    """GET does not retry on permanent (4xx) errors."""
    client = _VikingClient("https://example.com")
    call_count = [0]

    def always_4xx(url, **kwargs):
        call_count[0] += 1
        return SimpleNamespace(
            status_code=404,
            text="not found",
            json=lambda: {"status": "error", "error": {"code": "NOT_FOUND", "message": "missing"}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(client._httpx, "get", always_4xx)

    with pytest.raises(OpenVikingPermanentError, match="NOT_FOUND"):
        client.get("/api/v1/test")

    assert call_count[0] == 1


def test_viking_client_post_retries_on_transient_error(monkeypatch):
    """POST retries on transient (5xx) errors and succeeds on retry."""
    client = _VikingClient("https://example.com")
    call_count = [0]

    def failing_post(url, **kwargs):
        call_count[0] += 1
        if call_count[0] < 2:
            return SimpleNamespace(
                status_code=503,
                text="unavailable",
                json=lambda: {"status": "error", "error": {"code": "BUSY", "message": "retry"}},
                raise_for_status=lambda: None,
            )
        return SimpleNamespace(
            status_code=200,
            text="ok",
            json=lambda: {"result": {"created": True}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(client._httpx, "post", failing_post)

    result = client.post("/api/v1/test", {"key": "value"})
    assert result == {"result": {"created": True}}
    assert call_count[0] == 2


def test_viking_client_post_does_not_retry_on_permanent_error(monkeypatch):
    """POST does not retry on permanent (4xx) errors."""
    client = _VikingClient("https://example.com")
    call_count = [0]

    def always_4xx(url, **kwargs):
        call_count[0] += 1
        return SimpleNamespace(
            status_code=403,
            text="forbidden",
            json=lambda: {"status": "error", "error": {"code": "FORBIDDEN", "message": "denied"}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(client._httpx, "post", always_4xx)

    with pytest.raises(OpenVikingPermanentError, match="FORBIDDEN"):
        client.post("/api/v1/test", {"key": "value"})

    assert call_count[0] == 1


def test_viking_client_get_exhausts_retries_on_persistent_transient_error(monkeypatch):
    """GET exhausts all retries on persistent 5xx and then raises."""
    client = _VikingClient("https://example.com")
    call_count = [0]

    def always_5xx(url, **kwargs):
        call_count[0] += 1
        return SimpleNamespace(
            status_code=503,
            text="always unavailable",
            json=lambda: {"status": "error", "error": {"code": "BUSY", "message": "retry"}},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(client._httpx, "get", always_5xx)

    with pytest.raises(OpenVikingTransientError):
        client.get("/api/v1/test")

    assert call_count[0] == 3  # 3 retry attempts by default


def test_viking_client_health_returns_false_on_network_error(monkeypatch):
    """health() returns False when network error occurs."""
    client = _VikingClient("https://example.com")

    def network_error(url, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(client._httpx, "get", network_error)

    assert client.health() is False


# ---------------------------------------------------------------------------
# Tests for _tool_remember
# ---------------------------------------------------------------------------
# Tests for _tool_remember
# ---------------------------------------------------------------------------

def test_tool_remember_stores_content_with_default_category():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._user = "testuser"
    provider._agent = "hermes"
    provider._client.post.return_value = {
        "result": {"written_bytes": 42}
    }

    result = json.loads(provider._tool_remember({"content": "user prefers concise responses"}))

    assert result["status"] == "stored"
    assert "42b" in result["message"]
    provider._client.post.assert_called_once()
    call_args = provider._client.post.call_args
    assert call_args[0][0] == "/api/v1/content/write"
    assert "preferences" in call_args[0][1]["uri"]


def test_tool_remember_stores_content_with_explicit_category():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._user = "testuser"
    provider._agent = "hermes"
    provider._client.post.return_value = {
        "result": {"written_bytes": 100}
    }

    result = json.loads(provider._tool_remember({
        "content": "meeting scheduled for Monday",
        "category": "event"
    }))

    assert result["status"] == "stored"
    call_args = provider._client.post.call_args
    assert "events" in call_args[0][1]["uri"]


def test_tool_remember_rejects_empty_content():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._user = "testuser"
    provider._agent = "hermes"

    result = json.loads(provider._tool_remember({"content": ""}))

    assert "error" in result
    assert "content is required" in result["error"].lower()


def test_tool_remember_handles_server_error():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._user = "testuser"
    provider._agent = "hermes"
    provider._client.post.side_effect = RuntimeError("Connection refused")

    result = json.loads(provider._tool_remember({"content": "test memory"}))

    assert "error" in result


# ---------------------------------------------------------------------------
# Tests for handle_tool_call
# ---------------------------------------------------------------------------

def test_handle_tool_call_dispatches_to_search():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.post.return_value = {
        "result": {"memories": [], "resources": [], "skills": [], "total": 0}
    }

    result = provider.handle_tool_call("viking_search", {"query": "test"})
    parsed = json.loads(result)

    assert "results" in parsed


def test_handle_tool_call_dispatches_to_read():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.get.return_value = {"result": {"content": "test content"}}

    result = provider.handle_tool_call("viking_read", {
        "uri": "viking://user/test",
        "level": "overview"
    })
    parsed = json.loads(result)

    assert parsed["content"] == "test content"


def test_handle_tool_call_dispatches_to_browse():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.get.return_value = {"result": {"entries": []}}

    result = provider.handle_tool_call("viking_browse", {
        "action": "list",
        "path": "viking://"
    })
    parsed = json.loads(result)

    assert "entries" in parsed or "path" in parsed


def test_handle_tool_call_dispatches_to_remember():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._user = "testuser"
    provider._agent = "hermes"
    provider._client.post.return_value = {"result": {"written_bytes": 10}}

    result = provider.handle_tool_call("viking_remember", {"content": "test"})
    parsed = json.loads(result)

    assert parsed["status"] == "stored"


def test_handle_tool_call_dispatches_to_add_resource():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.post.return_value = {"status": "ok"}

    result = provider.handle_tool_call("viking_add_resource", {
        "url": "https://example.com/doc"
    })
    parsed = json.loads(result)

    assert "added" in parsed["status"].lower() or parsed["status"] == "ok"


def test_handle_tool_call_unknown_tool_returns_error():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()

    result = provider.handle_tool_call("viking_nonexistent", {})
    parsed = json.loads(result)

    assert "error" in parsed


def test_handle_tool_call_no_client_returns_error():
    provider = OpenVikingMemoryProvider()
    provider._client = None

    result = provider.handle_tool_call("viking_search", {"query": "test"})
    parsed = json.loads(result)

    assert "error" in parsed
    assert "not connected" in parsed["error"].lower()


# ---------------------------------------------------------------------------
# Tests for is_available
# ---------------------------------------------------------------------------

def test_is_available_returns_true_when_endpoint_set(monkeypatch):
    monkeypatch.setenv("OPENVIKING_ENDPOINT", "http://localhost:1933")
    provider = OpenVikingMemoryProvider()
    assert provider.is_available() is True


def test_is_available_returns_false_when_endpoint_not_set(monkeypatch):
    monkeypatch.delenv("OPENVIKING_ENDPOINT", raising=False)
    provider = OpenVikingMemoryProvider()
    assert provider.is_available() is False


def test_is_available_returns_false_when_endpoint_is_empty(monkeypatch):
    monkeypatch.setenv("OPENVIKING_ENDPOINT", "")
    provider = OpenVikingMemoryProvider()
    assert provider.is_available() is False


# ---------------------------------------------------------------------------
# Tests for viking_delete tool
# ---------------------------------------------------------------------------

def test_tool_delete_success():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.delete.return_value = {"status": "ok"}

    result = json.loads(provider._tool_delete({
        "uri": "viking://user/test/doc.md",
        "confirm": True,
    }))

    assert result["status"] == "deleted"
    assert result["uri"] == "viking://user/test/doc.md"
    provider._client.delete.assert_called_once_with(
        "/api/v1/fs/delete", params={"uri": "viking://user/test/doc.md"}
    )


def test_tool_delete_empty_uri_returns_error():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()

    result = json.loads(provider._tool_delete({
        "uri": "",
        "confirm": True,
    }))

    assert "error" in result
    provider._client.delete.assert_not_called()


def test_tool_delete_without_confirm_returns_error():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()

    result = json.loads(provider._tool_delete({
        "uri": "viking://user/test/doc.md",
        "confirm": False,
    }))

    assert "error" in result
    assert "confirm" in result["error"].lower()
    provider._client.delete.assert_not_called()


def test_tool_delete_network_error_returns_error():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.delete.side_effect = OpenVikingTransientError("network failure")

    result = json.loads(provider._tool_delete({
        "uri": "viking://user/test/doc.md",
        "confirm": True,
    }))

    assert "error" in result
    assert "delete failed" in result["error"].lower()


def test_handle_tool_call_dispatches_to_delete():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.delete.return_value = {"status": "ok"}

    result = provider.handle_tool_call("viking_delete", {
        "uri": "viking://user/test/doc.md",
        "confirm": True,
    })
    parsed = json.loads(result)

    assert parsed["status"] == "deleted"


# ---------------------------------------------------------------------------
# sync_turn
# ---------------------------------------------------------------------------


def test_sync_turn_starts_background_thread():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._client.post.return_value = {"status": "ok"}

    initial_thread = provider._sync_thread
    provider.sync_turn("hello", "hi there")

    assert provider._sync_thread is not None
    assert provider._sync_thread is not initial_thread


def test_sync_turn_handles_no_client():
    provider = OpenVikingMemoryProvider()
    provider._client = None

    provider.sync_turn("hello", "hi there")
    assert provider._turn_count == 0


# ---------------------------------------------------------------------------
# prefetch
# ---------------------------------------------------------------------------


def test_prefetch_returns_empty_when_no_results():
    provider = OpenVikingMemoryProvider()
    provider._client = MagicMock()
    provider._prefetch_thread = None
    provider._prefetch_result = ""

    result = provider.prefetch("test query")
    assert result == ""


# ---------------------------------------------------------------------------
# system_prompt_block
# ---------------------------------------------------------------------------


def test_system_prompt_block_returns_empty_when_unavailable():
    provider = OpenVikingMemoryProvider()
    provider._client = None

    result = provider.system_prompt_block()
    assert result == ""


# ---------------------------------------------------------------------------
# environment variable configuration
# ---------------------------------------------------------------------------


def test_configurable_timeout_from_env(monkeypatch):
    monkeypatch.setenv("OPENVIKING_TIMEOUT", "60.0")
    import importlib
    import plugins.memory.openviking as ov
    importlib.reload(ov)
    assert ov._OPENVIKING_TIMEOUT == 60.0
    importlib.reload(ov)


def test_configurable_retry_attempts_from_env(monkeypatch):
    monkeypatch.setenv("OPENVIKING_RETRY_ATTEMPTS", "5")
    import importlib
    import plugins.memory.openviking as ov
    importlib.reload(ov)
    assert ov._OPENVIKING_RETRY_ATTEMPTS == 5
    importlib.reload(ov)


def test_default_timeout_when_env_not_set(monkeypatch):
    monkeypatch.delenv("OPENVIKING_TIMEOUT", raising=False)
    import importlib
    import plugins.memory.openviking as ov
    importlib.reload(ov)
    assert ov._OPENVIKING_TIMEOUT == 30.0
    importlib.reload(ov)


def test_default_pool_limits(monkeypatch):
    monkeypatch.delenv("OPENVIKING_MAX_CONNECTIONS", raising=False)
    monkeypatch.delenv("OPENVIKING_MAX_KEEPALIVE", raising=False)
    monkeypatch.delenv("OPENVIKING_KEEPALIVE_EXPIRY", raising=False)
    import importlib
    import plugins.memory.openviking as ov
    importlib.reload(ov)
    assert ov._OPENVIKING_MAX_CONNECTIONS == 100
    assert ov._OPENVIKING_MAX_KEEPALIVE == 20
    assert ov._OPENVIKING_KEEPALIVE_EXPIRY == 30.0
    importlib.reload(ov)


def test_pool_limits_from_env(monkeypatch):
    monkeypatch.setenv("OPENVIKING_MAX_CONNECTIONS", "50")
    monkeypatch.setenv("OPENVIKING_MAX_KEEPALIVE", "10")
    monkeypatch.setenv("OPENVIKING_KEEPALIVE_EXPIRY", "15.0")
    import importlib
    import plugins.memory.openviking as ov
    importlib.reload(ov)
    assert ov._OPENVIKING_MAX_CONNECTIONS == 50
    assert ov._OPENVIKING_MAX_KEEPALIVE == 10
    assert ov._OPENVIKING_KEEPALIVE_EXPIRY == 15.0
    importlib.reload(ov)


def test_viking_client_uses_connection_pool():
    client = _VikingClient("http://127.0.0.1:1933")
    assert client._httpx is not None
    import httpx
    assert isinstance(client._httpx, httpx.Client)
