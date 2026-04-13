"""OpenAPI adapter — discovers and invokes OpenAPI-described APIs."""

from __future__ import annotations

from typing import Any

from loguru import logger

from sol.adapter import Adapter, ExecutionResult
from sol.client import AsyncHTTPClient
from sol.schema import Operation, OperationDetail, Parameter


class OpenAPIAdapter(Adapter):
    """Adapter for OpenAPI 3.x and Swagger 2.x APIs.

    Detection: Fetches the URL and checks for an OpenAPI or Swagger
    schema marker in the JSON response.
    """

    # ──────────────────────────────────────────────
    # Identity & Priority
    # ──────────────────────────────────────────────

    async def protocol_name(self) -> str:
        return "openapi"

    async def priority(self) -> int:
        return 200  # Higher priority — try before generic adapters

    # ──────────────────────────────────────────────
    # Detection
    # ──────────────────────────────────────────────

    async def can_handle(self, url: str) -> bool:
        """Probe the URL for an OpenAPI/Swagger schema.

        Returns True if the response contains 'openapi' or 'swagger'
        as a top-level key.
        """
        try:
            async with AsyncHTTPClient(timeout=10.0) as client:
                resp = await client.get(self._schema_url(url))
                if not resp.is_success or resp.json_body is None:
                    return False
                return "openapi" in resp.json_body or "swagger" in resp.json_body
        except Exception:
            logger.debug("OpenAPI detection failed for {}", url, exc_info=True)
            return False

    # ──────────────────────────────────────────────
    # Discovery
    # ──────────────────────────────────────────────

    async def list_operations(self, url: str) -> list[Operation]:
        """Parse the OpenAPI schema and return all operations."""
        schema = await self._fetch_schema(url)
        operations: list[Operation] = []

        paths = schema.get("paths", {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.startswith("x-") or method == "parameters":
                    continue
                op_id = details.get("operationId", f"{method}:{path}")
                operations.append(
                    Operation(
                        operation_id=op_id,
                        display_name=details.get("summary"),
                        description=details.get("description"),
                    )
                )

        return operations

    # ──────────────────────────────────────────────
    # Inspection
    # ──────────────────────────────────────────────

    async def describe_operation(self, url: str, op_id: str) -> OperationDetail:
        """Return detailed info about a specific operation."""
        schema = await self._fetch_schema(url)
        method, path, details = self._find_operation(schema, op_id)

        params: list[Parameter] = []
        for p in details.get("parameters", []):
            params.append(
                Parameter(
                    name=p["name"],
                    param_type=p.get("schema", {}).get("type", "string"),
                    required=p.get("required", False),
                    description=p.get("description"),
                )
            )

        return OperationDetail(
            operation_id=op_id,
            display_name=details.get("summary"),
            description=details.get("description"),
            parameters=params,
            return_type=self._extract_return_type(details),
        )

    # ──────────────────────────────────────────────
    # Execution
    # ──────────────────────────────────────────────

    async def execute(
        self,
        url: str,
        op_id: str,
        args: dict[str, Any],
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Invoke an OpenAPI operation."""
        schema = await self._fetch_schema(url)
        method, path, details = self._find_operation(schema, op_id)

        # Resolve path parameters
        resolved_path = path
        for p in details.get("parameters", []):
            if p.get("in") == "path" and p["name"] in args:
                resolved_path = resolved_path.replace(
                    f"{{{p['name']}}}", str(args.pop(p["name"]))
                )

        # Build the request URL
        base_url = self._base_url(schema, url)
        request_url = f"{base_url}{resolved_path}"

        async with AsyncHTTPClient(auth_headers=auth_headers) as client:
            if method in ("get", "delete", "head"):
                resp = await client.get(request_url, params=args or None)
            else:
                resp = await client.post(request_url, json=args or None)

        return ExecutionResult(
            data=resp.json_body if resp.json_body is not None else resp.text,
            status_code=resp.status_code,
            headers=resp.headers,
        )

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    def _schema_url(self, url: str) -> str:
        """Ensure the URL has a scheme."""
        if not url.startswith(("http://", "https://")):
            return f"https://{url}"
        return url

    async def _fetch_schema(self, url: str) -> dict[str, Any]:
        """Fetch and return the OpenAPI schema as a dict."""
        async with AsyncHTTPClient() as client:
            resp = await client.get(self._schema_url(url))
        if resp.json_body is None:
            from sol.errors import SchemaRetrievalError

            raise SchemaRetrievalError(f"No JSON response from {url}")
        return resp.json_body

    def _find_operation(
        self, schema: dict[str, Any], op_id: str
    ) -> tuple[str, str, dict[str, Any]]:
        """Find an operation by ID in the schema. Returns (method, path, details)."""
        for path, methods in schema.get("paths", {}).items():
            for method, details in methods.items():
                if method.startswith("x-") or method == "parameters":
                    continue
                found_id = details.get("operationId", f"{method}:{path}")
                if found_id == op_id:
                    return method, path, details
        from sol.errors import OperationNotFoundError

        raise OperationNotFoundError(f"Operation '{op_id}' not found in schema")

    def _base_url(self, schema: dict[str, Any], fallback: str) -> str:
        """Extract the base URL from the schema or fall back to the input URL."""
        servers = schema.get("servers", [])
        if servers:
            return servers[0].get("url", self._schema_url(fallback))
        return self._schema_url(fallback)

    def _extract_return_type(self, details: dict[str, Any]) -> str | None:
        """Extract the response content type from the operation details."""
        responses = details.get("responses", {})
        for status, resp in responses.items():
            if status.startswith("2"):
                content = resp.get("content", {})
                if content:
                    return next(iter(content.keys()), None)
        return None
