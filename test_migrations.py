from pathlib import Path
from datetime import datetime,timezone
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Text, Boolean, Float, DateTime, inspect, select
from backend.app.config import settings

def test_alembic_upgrades_an_unversioned_mvp_database(tmp_path):
    path=tmp_path/'legacy.sqlite';url=f"sqlite:///{path.as_posix()}"
    engine=create_engine(url);meta=MetaData()
    users=Table('users',meta,Column('id',Integer,primary_key=True),Column('name',String(120),nullable=False),Column('email',String(255),nullable=False),Column('hashed_password',String(255),nullable=False),Column('role',String(20),nullable=False),Column('team',String(80)),Column('is_active',Boolean,nullable=False),Column('created_at',DateTime(timezone=True),nullable=False))
    tickets=Table('tickets',meta,Column('id',Integer,primary_key=True),Column('customer_id',Integer,nullable=False),Column('assigned_agent_id',Integer),Column('subject',String(240),nullable=False),Column('description',Text,nullable=False),Column('category',String(80),nullable=False),Column('intent',String(80),nullable=False),Column('priority',String(20),nullable=False),Column('status',String(24),nullable=False),Column('sentiment',String(20),nullable=False),Column('language',String(20),nullable=False),Column('ai_confidence',Float,nullable=False),Column('created_at',DateTime(timezone=True),nullable=False),Column('updated_at',DateTime(timezone=True),nullable=False),Column('resolved_at',DateTime(timezone=True)),Column('escalated_at',DateTime(timezone=True)))
    docs=Table('knowledge_documents',meta,Column('id',Integer,primary_key=True),Column('title',String(240),nullable=False),Column('filename',String(255),nullable=False),Column('document_type',String(20),nullable=False),Column('uploaded_by',Integer,nullable=False),Column('created_at',DateTime(timezone=True),nullable=False))
    chunks=Table('knowledge_chunks',meta,Column('id',Integer,primary_key=True),Column('document_id',Integer,nullable=False),Column('content',Text,nullable=False),Column('chunk_index',Integer,nullable=False),Column('embedding_reference',String(120)))
    meta.create_all(engine)
    with engine.begin() as conn:conn.execute(users.insert().values(id=1,name='Legacy agent',email='legacy@example.com',hashed_password='hash',role='agent',team='Billing',is_active=True,created_at=datetime.now(timezone.utc)))
    previous=settings.database_url;settings.database_url=url
    try:
        cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'));command.upgrade(cfg,'head')
        names=inspect(engine).get_table_names()
        assert 'teams' in names and 'routing_rules' in names and 'supportiq_legacy_upgrade' in names
        assert {'team_id'} <= {c['name'] for c in inspect(engine).get_columns('users')}
        assert {'assigned_team_id','routing_reason'} <= {c['name'] for c in inspect(engine).get_columns('tickets')}
        with engine.connect() as conn:
            teams=Table('teams',MetaData(),autoload_with=conn)
            team=conn.execute(select(teams.c.name).where(teams.c.name=='Billing')).first()
            assert team is not None
    finally:
        settings.database_url=previous;engine.dispose()
