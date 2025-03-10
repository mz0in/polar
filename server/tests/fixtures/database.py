from collections.abc import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from pytest_mock import MockerFixture
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from polar.kit.db.postgres import AsyncEngine, AsyncSession
from polar.kit.extensions.sqlalchemy import PostgresUUID
from polar.kit.utils import generate_uuid
from polar.models import Model
from polar.postgres import create_engine


class TestModel(Model):
    __test__ = False  # This is a base class, not a test

    __tablename__ = "test_model"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=None)
    uuid: Mapped[UUID] = mapped_column(PostgresUUID, default=generate_uuid)
    int_column: Mapped[int | None] = mapped_column(Integer, default=None, nullable=True)
    str_column: Mapped[str | None] = mapped_column(String, default=None, nullable=True)


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_engine("app")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def initialize_test_database(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Model.metadata.create_all)


@pytest_asyncio.fixture
async def session(
    engine: AsyncEngine,
    mocker: MockerFixture,
    request: pytest.FixtureRequest,
) -> AsyncIterator[AsyncSession]:
    connection = await engine.connect()
    transaction = await connection.begin()

    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    expunge_spy = mocker.spy(session, "expunge_all")

    yield session

    await transaction.rollback()
    await connection.close()

    skip_db_assert_marker = request.node.get_closest_marker("skip_db_asserts")
    if skip_db_assert_marker is not None:
        return

    # Assert that session.expunge_all() was called.
    #
    # expunge_all() should be called after the test has been setup, and before
    # the test calls out to the implementation.
    #
    # This is to ensure that we don't rely on the existing state in the Session
    # from creating the tests.
    expunge_spy.assert_called()
