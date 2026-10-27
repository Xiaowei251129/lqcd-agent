"""Identify the exact CSV bytes consumed by a scientific calculation."""
import csv
import hashlib
import io
import os
from pathlib import Path


def dataset_path(workspace, relative):
    root = Path(workspace).resolve()
    path = Path(str(relative))
    resolved = (root / path).resolve()
    if path.is_absolute() or not resolved.is_relative_to((root / 'raw_data').resolve()):
        raise ValueError('raw_data_path must stay under workspace raw_data/.')
    return resolved


def read_dataset(workspace, relative, *, text_columns=(), values=False):
    """Hash and parse one stream; never re-hash a path after computation."""
    path = dataset_path(workspace, relative)
    record = {'path': str(relative), 'exists': False, 'sha256': None, 'bytes': None, 'columns': []}
    columns = {}
    if path.exists() and not path.is_file():
        raise ValueError('raw_data_path is not a regular file.')
    try:
        handle = path.open('rb')
    except FileNotFoundError:
        return record, columns
    with handle:
        before = os.fstat(handle.fileno())
        digest, size = hashlib.sha256(), 0

        class DigestReader(io.RawIOBase):
            def readable(self):
                return True

            def readinto(self, buffer):
                nonlocal size
                count = handle.readinto(buffer)
                digest.update(memoryview(buffer)[:count])
                size += count
                return count

        with io.TextIOWrapper(io.BufferedReader(DigestReader()), encoding='utf-8', newline='') as source:
            reader = csv.reader(source)
            header = next(reader, [])
            if values:
                if not header or len(set(header)) != len(header):
                    raise ValueError('Raw CSV requires a nonempty header with unique columns.')
                columns = {field: [] for field in header}
                for row in reader:
                    if not row:
                        continue
                    if len(row) != len(header):
                        raise ValueError(f'Raw CSV row {reader.line_num} has the wrong number of columns.')
                    for field, value in zip(header, row, strict=True):
                        try:
                            columns[field].append(value if field in text_columns else float(value))
                        except ValueError:
                            raise ValueError(f'Raw CSV column {field} has a non-numeric value on row {reader.line_num}.') from None
            else:
                for _ in source:
                    pass
        after = os.fstat(handle.fileno())
        identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if identity(before) != identity(after) or size != after.st_size:
            raise ValueError('Raw data changed while being read.')
    record.update(exists=True, sha256=digest.hexdigest(), bytes=size, columns=header)
    return record, columns


def snapshot_dataset(config, workspace):
    relative = config.get('raw_data_path')
    return read_dataset(workspace, relative)[0] if relative else None
