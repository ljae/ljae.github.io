"""Local private ingestion ledger. Original snapshots retain their own grain."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""create table if not exists snapshots (
          id text primary key, property text not null, checksum text not null,
          kind text not null, start text not null, end text not null,
          payload text not null, unique(property, checksum))""")
        self.db.commit()
        self.db.execute("""create table if not exists api_partitions (
          property text, search_type text, day text, payload text not null,
          primary key(property, search_type, day))""")
        self.db.commit()

    def put_partition(self, property_id, search_type, day, payload):
        with self.db:
            self.db.execute("insert into api_partitions values(?,?,?,?) on conflict(property,search_type,day) do update set payload=excluded.payload",
                            (property_id, search_type, day, json.dumps(payload, ensure_ascii=False)))

    def partitions(self, property_id, search_type, start, end):
        return {r['day']: json.loads(r['payload']) for r in self.db.execute(
            "select day,payload from api_partitions where property=? and search_type=? and day between ? and ?",
            (property_id, search_type, start, end))}

    def import_snapshot(self, snapshot: dict) -> tuple[str, bool]:
        from .contracts import stable_hash
        key = stable_hash([snapshot["property"], snapshot["checksum"]])
        with self.db:
            cursor = self.db.execute(
                "insert or ignore into snapshots values(?,?,?,?,?,?,?)",
                (key, snapshot["property"], snapshot["checksum"], snapshot["kind"],
                 snapshot["period"]["start"], snapshot["period"]["end"],
                 json.dumps(snapshot, ensure_ascii=False)))
        return key, bool(cursor.rowcount)

    def snapshots(self, property_id: str, kind="performance") -> list[dict]:
        return [dict(id=r["id"], **json.loads(r["payload"])) for r in self.db.execute(
            "select id,payload from snapshots where property=? and kind=? order by end desc,start desc,case when json_extract(payload,'$.source')='gsc_api_final' then 0 else 1 end,json_extract(payload,'$.exportedAt') desc,rowid desc",
            (property_id, kind))]

    def close(self):
        self.db.close()
