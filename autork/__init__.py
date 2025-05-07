from importlib.metadata import version as _get_version, PackageNotFoundError

try:
    # Берём номер версии из метаданных установленного пакета
    __version__ = _get_version(__name__)
except PackageNotFoundError:
    # Если пакет ещё не установлен (например, запускаете из репозитория)
    __version__ = "0.0.0-dev"

# По желанию: предоставить короткий алиас
version = __version__

# Очистим вспомогательные имена, чтобы не светились в dir()
del _get_version, PackageNotFoundError