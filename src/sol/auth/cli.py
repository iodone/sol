"""CLI subcommands for auth management: sol auth set/list/remove/bind."""

from __future__ import annotations

from typing import Optional

import typer

from sol.auth.binding import AuthBinding, AuthBindings
from sol.auth.profile import AuthType, EnvSecret, LiteralSecret, Profile, Profiles

auth_app = typer.Typer(
    name="auth",
    help="Manage authentication profiles and bindings.",
    no_args_is_help=True,
)


@auth_app.command("set")
def auth_set(
    name: str = typer.Argument(..., help="Profile name"),
    auth_type: AuthType = typer.Option(
        AuthType.bearer, "--type", "-t", help="Auth type"
    ),
    secret: Optional[str] = typer.Option(
        None, "--secret", "-s", help="Secret value (literal)"
    ),
    env: Optional[str] = typer.Option(
        None, "--env", "-e", help="Environment variable name for the secret"
    ),
    description: str = typer.Option(
        "", "--description", "-d", help="Profile description"
    ),
) -> None:
    """Create or update an auth profile."""
    if secret and env:
        typer.echo("Error: specify either --secret or --env, not both", err=True)
        raise typer.Exit(code=1)
    if not secret and not env:
        typer.echo("Error: specify --secret or --env for the credential", err=True)
        raise typer.Exit(code=1)

    if secret:
        source = LiteralSecret(value=secret)
    else:
        source = EnvSecret(key=env)  # type: ignore[arg-type]

    profile = Profile(
        name=name,
        auth_type=auth_type,
        secret_source=source,
        description=description,
    )

    store = Profiles()
    store.load()
    store.set_profile(profile)
    store.save()
    typer.echo(f"Profile '{name}' saved ({auth_type.value})")


@auth_app.command("list")
def auth_list() -> None:
    """List all auth profiles."""
    store = Profiles()
    store.load()
    profiles = store.list_profiles()
    if not profiles:
        typer.echo("No profiles configured.")
        return
    for p in profiles:
        source_info = (
            f"env:{p.secret_source.key}"
            if hasattr(p.secret_source, "key")
            else "literal:***"
        )
        desc = f" — {p.description}" if p.description else ""
        typer.echo(f"  {p.name}  [{p.auth_type.value}]  ({source_info}){desc}")


@auth_app.command("remove")
def auth_remove(
    name: str = typer.Argument(..., help="Profile name to remove"),
) -> None:
    """Remove an auth profile."""
    store = Profiles()
    store.load()
    if store.remove_profile(name):
        store.save()
        typer.echo(f"Profile '{name}' removed.")
    else:
        typer.echo(f"Profile '{name}' not found.", err=True)
        raise typer.Exit(code=1)


@auth_app.command("bind")
def auth_bind(
    host: str = typer.Argument(..., help="Host glob pattern (e.g. '*.example.com')"),
    credential: str = typer.Argument(..., help="Profile name to bind"),
    alias: Optional[str] = typer.Option(
        None, "--alias", "-a", help="Short alias for this host (e.g. 'prod')"
    ),
    priority: int = typer.Option(
        0, "--priority", "-p", help="Binding priority (higher wins)"
    ),
    meta: Optional[list[str]] = typer.Option(
        None, "--meta", "-m", help="Metadata key=value pairs (e.g., --meta region=chnbj)"
    ),
) -> None:
    """Bind a host pattern to an auth profile."""
    # Validate alias format
    if alias and "/" in alias:
        typer.echo(
            "Warning: Alias contains '/' which will be interpreted as a URL path separator.",
            err=True,
        )
        typer.echo(
            f"  URL 'echo://{alias}' → hostname='{alias.split('/')[0]}', path='/{alias.split('/', 1)[1]}'",
            err=True,
        )
        typer.echo(
            "  Recommended: Use '-' or '.' instead (e.g., 'region-us' or 'region.us')",
            err=True,
        )
        if not typer.confirm("Continue anyway?", default=False):
            raise typer.Abort()

    # Parse meta key=value pairs
    meta_dict: dict[str, str] | None = None
    if meta:
        meta_dict = {}
        for item in meta:
            if "=" not in item:
                typer.echo(f"Error: Invalid meta format '{item}' (expected key=value)", err=True)
                raise typer.Exit(code=1)
            key, value = item.split("=", 1)
            meta_dict[key.strip()] = value.strip()

    binding = AuthBinding(
        host=host, credential=credential, alias=alias, priority=priority, meta=meta_dict
    )
    bindings = AuthBindings()
    bindings.load()
    bindings.add_binding(binding)
    bindings.save()
    alias_info = f" (alias: {alias})" if alias else ""
    meta_info = f" meta={meta_dict}" if meta_dict else ""
    typer.echo(f"Bound '{host}' → '{credential}'{alias_info}{meta_info} (priority {priority})")


@auth_app.command("unbind")
def auth_unbind(
    host: str = typer.Argument(..., help="Host glob pattern"),
    credential: str = typer.Argument(..., help="Profile name"),
) -> None:
    """Remove a host-to-credential binding."""
    bindings = AuthBindings()
    bindings.load()
    if bindings.remove_binding(host, credential):
        bindings.save()
        typer.echo(f"Unbound '{host}' ↛ '{credential}'")
    else:
        typer.echo("No matching binding found.", err=True)
        raise typer.Exit(code=1)


@auth_app.command("bindings")
def auth_bindings_list() -> None:
    """List all auth bindings."""
    bindings = AuthBindings()
    bindings.load()
    items = bindings.list_bindings()
    if not items:
        typer.echo("No bindings configured.")
        return
    for b in items:
        alias_info = f" (alias: {b.alias})" if b.alias else ""
        typer.echo(f"  {b.host} → {b.credential}{alias_info}  (priority {b.priority})")
