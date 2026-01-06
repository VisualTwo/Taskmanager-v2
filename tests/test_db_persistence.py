import uuid
import json
import sqlite3

from infrastructure.db_repository import DbRepository
from domain.models import Task
from utils.datetime_helpers import format_db_datetime, now_utc


def make_repo():
    return DbRepository(':memory:')


def test_upsert_and_row_to_item_roundtrip():
    repo = make_repo()
    item = Task(id=str(uuid.uuid4()), type='task', name='Roundtrip', status='TASK_OPEN', is_private=False,
                metadata={'foo': 'bar', 'ice_impact': '4', 'ice_confidence': 'medium', 'ice_ease': '5', 'ice_score': '10.0'})
    repo.upsert(item)
    repo.conn.commit()

    loaded = repo.get(item.id)
    assert loaded is not None
    assert loaded.id == item.id
    assert loaded.name == 'Roundtrip'
    meta = getattr(loaded, 'metadata', {}) or {}
    assert meta.get('foo') == 'bar'
    assert meta.get('ice_impact') == '4'
    assert meta.get('ice_confidence') == 'medium'
    assert meta.get('ice_ease') == '5'
    assert meta.get('ice_score') == '10.0'


def test_ice_columns_check_constraints():
    repo = make_repo()
    cur = repo.conn.cursor()
    # insert minimal valid row but violate ice_impact constraint (set to 20)
    now = format_db_datetime(now_utc())
    with repo.conn:
        try:
            cur.execute(
                """INSERT INTO items (id,type,name,status_key,is_private,tags,links,created_utc,last_modified_utc,ice_impact)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), 'task', 'BadICE', 'TASK_OPEN', 0, '[]', '[]', now, now, 20),
            )
            # commit should raise due to CHECK
        except sqlite3.IntegrityError:
            # expected
            return
    # If we reach here, constraint didn't fire
    raise AssertionError('ICE CHECK constraint did not raise IntegrityError')


def test_persisting_ice_from_metadata_to_columns():
    repo = make_repo()
    item = Task(id=str(uuid.uuid4()), type='task', name='PersistICE', status='TASK_OPEN', is_private=False,
                metadata={'ice_impact': '5', 'ice_confidence': 'low', 'ice_ease': '6', 'ice_score': '9.0'})
    repo.upsert(item)
    repo.conn.commit()

    row = repo.conn.execute('SELECT ice_impact, ice_confidence, ice_ease, ice_score FROM items WHERE id=?', (item.id,)).fetchone()
    assert row is not None
    assert row['ice_impact'] == 5
    assert row['ice_confidence'] == 'low'
    assert row['ice_ease'] == 6
    assert abs(float(row['ice_score']) - 9.0) < 1e-6


def test_query_sort_by_ice_score():
    repo = make_repo()
    ids = []
    # create three items with different ice_score via metadata
    for score, impact, conf, ease in ((10.0, 5, 'medium', 4), (30.0, 6, 'high', 7), (5.0, 5, 'low', 2)):
        it = Task(id=str(uuid.uuid4()), type='task', name=f'Sort{score}', status='TASK_OPEN', is_private=False,
                  metadata={'ice_impact': str(impact), 'ice_confidence': conf, 'ice_ease': str(ease), 'ice_score': str(score)})
        repo.upsert(it)
        ids.append(it.id)
    repo.conn.commit()

    rows = repo.conn.execute('SELECT id, ice_score FROM items ORDER BY ice_score DESC').fetchall()
    scores = [float(r['ice_score']) for r in rows]
    assert scores == sorted(scores, reverse=True)


def test_backward_compatibility_metadata_only_items():
    repo = make_repo()
    cur = repo.conn.cursor()
    now = format_db_datetime(now_utc())
    item_id = str(uuid.uuid4())
    metadata = {'ice_impact': '3', 'ice_confidence': 'medium', 'ice_ease': '4', 'ice_score': '6.0', 'legacy':'yes'}
    cur.execute(
        """INSERT INTO items (id,type,name,status_key,is_private,tags,links,created_utc,last_modified_utc,metadata)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (item_id, 'task', 'Legacy', 'TASK_OPEN', 0, '[]', '[]', now, now, json.dumps(metadata)),
    )
    repo.conn.commit()

    loaded = repo.get(item_id)
    assert loaded is not None
    meta = getattr(loaded, 'metadata', {}) or {}
    # metadata values should be preserved even if ice_ columns are null
    assert meta.get('legacy') == 'yes'
    assert meta.get('ice_impact') == '3'
    assert meta.get('ice_confidence') == 'medium'
    assert meta.get('ice_ease') == '4'
    assert meta.get('ice_score') == '6.0'
