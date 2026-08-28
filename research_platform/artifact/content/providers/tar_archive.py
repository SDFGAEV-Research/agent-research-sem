from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from ..api.materialization import (
    ArchiveMaterializationError,
    ArchiveMaterializationPort,
    ArchiveMaterializationRequest,
    ArchiveMaterializationResult,
    MaterializedTreeInspection,
    MaterializedTreeInspectionPort,
)


def _safe_member_path(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or "\x00" in normalized
        or path.is_absolute()
        or any(part in ("", "..") for part in path.parts)
    ):
        raise ArchiveMaterializationError(
            "UNSAFE_MEMBER_PATH", f"unsafe archive member: {name!r}"
        )
    return path


def _safe_link_target(member_path: PurePosixPath, link_name: str) -> str:
    normalized = link_name.replace("\\", "/")
    target = PurePosixPath(normalized)
    if not normalized or "\x00" in normalized or target.is_absolute():
        raise ArchiveMaterializationError(
            "UNSAFE_LINK_TARGET",
            f"unsafe link target for {member_path}: {link_name!r}",
        )
    stack = list(member_path.parent.parts)
    for part in target.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if len(stack) <= 1:
                raise ArchiveMaterializationError(
                    "UNSAFE_LINK_TARGET",
                    f"link target escapes the single archive root for {member_path}: {link_name!r}",
                )
            stack.pop()
        else:
            stack.append(part)
    return normalized


def _safe_hardlink_target(link_name: str) -> PurePosixPath:
    normalized = link_name.replace("\\", "/")
    target = PurePosixPath(normalized)
    if (
        not normalized
        or "\x00" in normalized
        or target.is_absolute()
        or any(part in ("", "..") for part in target.parts)
    ):
        raise ArchiveMaterializationError(
            "UNSAFE_LINK_TARGET",
            f"unsafe archive-root-relative hardlink target: {link_name!r}",
        )
    return target


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def digest_materialized_tree(root: str | Path) -> tuple[str, int, int]:
    """Return a stable digest over paths, modes, links and regular-file bytes."""

    base = Path(root)
    if not base.is_dir() or base.is_symlink():
        raise ArchiveMaterializationError(
            "TREE_MISSING", f"materialized tree is missing: {base}"
        )
    digest = hashlib.sha256()
    file_count = 0
    expanded_size = 0
    rows: list[tuple[str, Path]] = []
    for directory, names, filenames in os.walk(base, followlinks=False):
        current = Path(directory)
        current_relative = current.relative_to(base)
        for name in names + filenames:
            path = current / name
            relative = (current_relative / name).as_posix()
            rows.append((relative, path))
    for relative, path in sorted(rows, key=lambda item: item[0]):
        metadata = path.lstat()
        mode = stat.S_IMODE(metadata.st_mode) & 0o777
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(f"{mode:o}".encode("ascii"))
        digest.update(b"\0")
        if stat.S_ISLNK(metadata.st_mode):
            digest.update(b"link\0")
            digest.update(os.readlink(path).encode("utf-8"))
        elif stat.S_ISDIR(metadata.st_mode):
            digest.update(b"dir")
        elif stat.S_ISREG(metadata.st_mode):
            digest.update(b"file\0")
            file_digest, size = _sha256_file(path)
            digest.update(file_digest.encode("ascii"))
            file_count += 1
            expanded_size += size
        else:
            raise ArchiveMaterializationError(
                "TREE_ENTRY_UNSUPPORTED",
                f"unsupported materialized tree entry: {relative}",
            )
        digest.update(b"\0")
    return digest.hexdigest(), file_count, expanded_size


class SafeTarArchiveMaterializer(
    ArchiveMaterializationPort,
    MaterializedTreeInspectionPort,
):
    """Fail-closed tar materializer with bounded, atomic tree publication."""

    def inspect(self, root: str) -> MaterializedTreeInspection:
        tree_sha256, file_count, expanded_size = digest_materialized_tree(root)
        return MaterializedTreeInspection(tree_sha256, file_count, expanded_size)

    def materialize(
        self,
        request: ArchiveMaterializationRequest,
    ) -> ArchiveMaterializationResult:
        archive_path = Path(request.archive_path).resolve()
        destination = Path(request.destination).resolve()
        if not archive_path.is_file():
            raise ArchiveMaterializationError(
                "ARCHIVE_MISSING", f"archive is missing: {archive_path}"
            )
        if destination.exists() or destination.is_symlink():
            raise ArchiveMaterializationError(
                "DESTINATION_EXISTS",
                f"materialization destination already exists: {destination}",
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.", dir=str(destination.parent)
            )
        )
        published = False
        try:
            with tarfile.open(archive_path, mode="r:*") as archive:
                members = archive.getmembers()
                if not members or len(members) > request.max_members:
                    raise ArchiveMaterializationError(
                        "MEMBER_LIMIT",
                        f"archive member count is outside 1..{request.max_members}",
                    )
                paths: dict[str, tuple[tarfile.TarInfo, PurePosixPath]] = {}
                expanded_size = 0
                for member in members:
                    member_path = _safe_member_path(member.name)
                    key = member_path.as_posix().rstrip("/")
                    if key in paths:
                        raise ArchiveMaterializationError(
                            "DUPLICATE_MEMBER", f"duplicate archive member: {key}"
                        )
                    if not (
                        member.isdir()
                        or member.isreg()
                        or member.issym()
                        or member.islnk()
                    ):
                        raise ArchiveMaterializationError(
                            "UNSUPPORTED_MEMBER_TYPE",
                            f"unsupported archive member type: {member.name}",
                        )
                    if member.isreg():
                        if member.size < 0:
                            raise ArchiveMaterializationError(
                                "MEMBER_SIZE_INVALID", member.name
                            )
                        expanded_size += member.size
                    paths[key] = (member, member_path)
                if expanded_size > request.max_expanded_size:
                    raise ArchiveMaterializationError(
                        "EXPANDED_SIZE_LIMIT",
                        f"archive expands to {expanded_size} bytes; limit={request.max_expanded_size}",
                    )
                roots = {path.parts[0] for _, path in paths.values() if path.parts}
                if len(roots) != 1:
                    raise ArchiveMaterializationError(
                        "TOP_LEVEL_LAYOUT",
                        "archive must contain exactly one top-level directory",
                    )
                top_level = next(iter(roots))
                top_entry = paths.get(top_level)
                if top_entry is not None and not top_entry[0].isdir():
                    raise ArchiveMaterializationError(
                        "TOP_LEVEL_LAYOUT",
                        "archive top-level entry must be a directory",
                    )

                directories: list[tuple[tarfile.TarInfo, Path]] = []
                for member, member_path in paths.values():
                    target = staging.joinpath(*member_path.parts)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True, mode=0o755)
                        directories.append((member, target))
                    elif member.isreg():
                        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                        source = archive.extractfile(member)
                        if source is None:
                            raise ArchiveMaterializationError(
                                "MEMBER_READ_FAILED",
                                f"regular archive member cannot be read: {member.name}",
                            )
                        with source, target.open("xb") as output:
                            shutil.copyfileobj(source, output, length=1024 * 1024)
                        target.chmod(member.mode & 0o777)

                for member, member_path in paths.values():
                    if not (member.issym() or member.islnk()):
                        continue
                    target = staging.joinpath(*member_path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                    if target.exists() or target.is_symlink():
                        raise ArchiveMaterializationError(
                            "LINK_COLLISION",
                            f"archive link collides with an extracted entry: {member.name}",
                        )
                    if member.issym():
                        link_name = _safe_link_target(member_path, member.linkname)
                        target.symlink_to(link_name)
                    else:
                        hardlink_target = _safe_hardlink_target(member.linkname)
                        hardlink_path = staging.joinpath(*hardlink_target.parts)
                        if not hardlink_path.is_file() or hardlink_path.is_symlink():
                            raise ArchiveMaterializationError(
                                "HARDLINK_TARGET_INVALID",
                                f"hardlink target is not an extracted regular file: {member.linkname}",
                            )
                        os.link(hardlink_path, target)

                for member, target in sorted(
                    directories,
                    key=lambda row: len(row[1].parts),
                    reverse=True,
                ):
                    target.chmod(member.mode & 0o777)

            candidate = staging / top_level
            if not candidate.is_dir() or candidate.is_symlink():
                raise ArchiveMaterializationError(
                    "TOP_LEVEL_LAYOUT", "archive root was not materialized"
                )
            for relative in request.required_relative_paths:
                required = candidate.joinpath(
                    *PurePosixPath(relative.replace("\\", "/")).parts
                )
                if not required.is_file():
                    raise ArchiveMaterializationError(
                        "REQUIRED_PATH_MISSING",
                        f"required archive path is missing: {relative}",
                    )
            tree_sha256, file_count, actual_size = digest_materialized_tree(candidate)
            candidate.replace(destination)
            published = True
            return ArchiveMaterializationResult(
                str(destination),
                top_level,
                tree_sha256,
                file_count,
                actual_size,
            )
        except ArchiveMaterializationError:
            raise
        except (OSError, tarfile.TarError) as exc:
            raise ArchiveMaterializationError(
                "MATERIALIZATION_FAILED",
                f"{type(exc).__name__}: {exc}",
            ) from exc
        finally:
            if staging.exists():
                shutil.rmtree(staging)
            if not published and destination.is_symlink():
                raise ArchiveMaterializationError(
                    "DESTINATION_DRIFT",
                    f"destination became a symlink during materialization: {destination}",
                )


__all__ = ["SafeTarArchiveMaterializer", "digest_materialized_tree"]
