from os import getenv


LOCAL_ENVIRONMENTS = {"local", "localhost"}


def _normalize_base_url(url: str) -> str:
    stripped_url = url.strip()
    return f"{stripped_url.rstrip('/')}/"


def _get_env_value(name: str, default: str) -> str:
    value = getenv(name, default).strip()
    return value or default


def get_environment_name() -> str:
    return getenv("ENVIRONMENT", "local").strip().lower() or "local"


def is_local_environment() -> bool:
    return get_environment_name() in LOCAL_ENVIRONMENTS


def _build_url(scheme: str, host: str, port: str | None = None) -> str:
    authority = host if not port else f"{host}:{port}"
    return _normalize_base_url(f"{scheme}://{authority}")


def get_backend_public_base_url() -> str:
    configured_url = getenv("HOST_URL", "").strip()

    if not is_local_environment() and configured_url:
        return _normalize_base_url(configured_url)

    if is_local_environment():
        return _build_url(
            scheme=_get_env_value("LOCAL_API_SCHEME", "http"),
            host=_get_env_value("LOCAL_API_HOST", "localhost"),
            port=_get_env_value("LOCAL_API_PORT", getenv("PORT", "5010") or "5010"),
        )

    if configured_url:
        return _normalize_base_url(configured_url)

    return _build_url(
        scheme=_get_env_value("API_SCHEME", "https"),
        host=_get_env_value("PUBLIC_API_HOST", "localhost"),
        port=getenv("PUBLIC_API_PORT", "").strip() or None,
    )


def get_frontend_public_base_url() -> str:
    configured_url = getenv("FRONT_URL", "").strip()
    if configured_url:
        return _normalize_base_url(configured_url)

    if is_local_environment():
        return _build_url(
            scheme=_get_env_value("FRONT_SCHEME", "http"),
            host=_get_env_value("LOCAL_FRONT_HOST", "localhost"),
            port=_get_env_value("LOCAL_FRONT_PORT", "8000"),
        )

    return _build_url(
        scheme=_get_env_value("FRONT_SCHEME", "https"),
        host=_get_env_value("PUBLIC_FRONT_HOST", "localhost"),
        port=getenv("PUBLIC_FRONT_PORT", "").strip() or None,
    )


def build_backend_url(path: str) -> str:
    return f"{get_backend_public_base_url()}{path.lstrip('/')}"


def build_frontend_url(path: str) -> str:
    return f"{get_frontend_public_base_url()}{path.lstrip('/')}"
