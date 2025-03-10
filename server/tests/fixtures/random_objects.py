import random
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest_asyncio

from polar.enums import AccountType, Platforms
from polar.integrations.github.service import (
    github_organization,
    github_repository,
)
from polar.kit.db.postgres import AsyncSession
from polar.kit.utils import utc_now
from polar.models import (
    Account,
    Organization,
    Repository,
    Subscription,
    SubscriptionBenefit,
    SubscriptionTier,
    SubscriptionTierBenefit,
    User,
    UserOrganization,
)
from polar.models.article import Article
from polar.models.issue import Issue
from polar.models.pledge import Pledge, PledgeState, PledgeType
from polar.models.pull_request import PullRequest
from polar.models.subscription import SubscriptionStatus
from polar.models.subscription_benefit import (
    SubscriptionBenefitType,
)
from polar.models.subscription_benefit_grant import SubscriptionBenefitGrant
from polar.models.subscription_tier import SubscriptionTierType
from polar.models.user import OAuthAccount
from polar.organization.schemas import OrganizationCreate
from polar.repository.schemas import RepositoryCreate


def rstr(prefix: str) -> str:
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


@pytest_asyncio.fixture(scope="function")
async def organization(session: AsyncSession) -> Organization:
    return await create_organization(session)


@pytest_asyncio.fixture(scope="function")
async def second_organization(session: AsyncSession) -> Organization:
    return await create_organization(session)


async def create_organization(session: AsyncSession) -> Organization:
    create_schema = OrganizationCreate(
        platform=Platforms.github,
        name=rstr("testorg"),
        external_id=secrets.randbelow(100000),
        avatar_url="https://avatars.githubusercontent.com/u/105373340?s=200&v=4",
        is_personal=False,
        installation_id=secrets.randbelow(100000),
        installation_created_at=datetime.now(),
        installation_updated_at=datetime.now(),
        installation_suspended_at=None,
    )

    org = await github_organization.create(session, create_schema)
    session.add(org)
    await session.commit()
    return org


@pytest_asyncio.fixture(scope="function")
async def pledging_organization(session: AsyncSession) -> Organization:
    create_schema = OrganizationCreate(
        platform=Platforms.github,
        name=rstr("pledging_org"),
        external_id=secrets.randbelow(100000),
        avatar_url="https://avatars.githubusercontent.com/u/105373340?s=200&v=4",
        is_personal=False,
        installation_id=secrets.randbelow(100000),
        installation_created_at=datetime.now(),
        installation_updated_at=datetime.now(),
        installation_suspended_at=None,
    )

    org = await github_organization.create(session, create_schema)
    session.add(org)
    await session.commit()
    return org


@pytest_asyncio.fixture(scope="function")
async def repository(session: AsyncSession, organization: Organization) -> Repository:
    return await create_repository(session, organization, is_private=True)


@pytest_asyncio.fixture(scope="function")
async def public_repository(
    session: AsyncSession, organization: Organization
) -> Repository:
    return await create_repository(session, organization, is_private=False)


async def create_repository(
    session: AsyncSession, organization: Organization, is_private: bool = True
) -> Repository:
    create_schema = RepositoryCreate(
        platform=Platforms.github,
        name=rstr("testrepo"),
        organization_id=organization.id,
        external_id=secrets.randbelow(100000),
        is_private=is_private,
    )
    repo = await github_repository.create(session, create_schema)
    session.add(repo)
    await session.commit()
    return repo


@pytest_asyncio.fixture(scope="function")
async def issue(
    session: AsyncSession, organization: Organization, repository: Repository
) -> Issue:
    return await create_issue(session, organization, repository)


async def create_issue(
    session: AsyncSession, organization: Organization, repository: Repository
) -> Issue:
    issue = await Issue(
        id=uuid.uuid4(),
        organization_id=organization.id,
        repository_id=repository.id,
        title="issue title",
        number=secrets.randbelow(100000),
        platform=Platforms.github,
        external_id=secrets.randbelow(100000),
        state="open",
        issue_created_at=datetime.now(),
        issue_modified_at=datetime.now(),
        external_lookup_key=str(uuid.uuid4()),  # not realistic
        issue_has_in_progress_relationship=False,
        issue_has_pull_request_relationship=False,
    ).save(
        session=session,
    )

    await session.commit()
    return issue


@pytest_asyncio.fixture(scope="function")
async def user_github_oauth(
    session: AsyncSession,
    user: User,
) -> OAuthAccount:
    a = await OAuthAccount(
        platform=Platforms.github,
        access_token="xxyyzz",
        account_id="xxyyzz",
        account_email="foo@bar.com",
        user_id=user.id,
    ).save(session)

    await session.commit()
    return a


@pytest_asyncio.fixture(scope="function")
async def user(
    session: AsyncSession,
) -> User:
    return await create_user(session)


async def create_user(
    session: AsyncSession,
) -> User:
    user = await User(
        id=uuid.uuid4(),
        username=rstr("testuser"),
        email=rstr("test") + "@example.com",
        avatar_url="https://avatars.githubusercontent.com/u/47952?v=4",
    ).save(session=session)

    await session.commit()
    return user


@pytest_asyncio.fixture(scope="function")
async def user_second(
    session: AsyncSession,
) -> User:
    user = await User(
        id=uuid.uuid4(),
        username=rstr("testuser"),
        email=rstr("test") + "@example.com",
        avatar_url="https://avatars.githubusercontent.com/u/47952?v=4",
    ).save(
        session=session,
    )

    await session.commit()
    return user


async def create_pledge(
    session: AsyncSession,
    organization: Organization,
    repository: Repository,
    issue: Issue,
    pledging_organization: Organization,
    *,
    state: PledgeState = PledgeState.created,
    type: PledgeType = PledgeType.pay_upfront,
) -> Pledge:
    amount = secrets.randbelow(100000) + 1
    fee = round(amount * 0.05)
    pledge = await Pledge(
        id=uuid.uuid4(),
        by_organization_id=pledging_organization.id,
        issue_id=issue.id,
        repository_id=repository.id,
        organization_id=organization.id,
        amount=amount,
        fee=fee,
        state=state,
        type=type,
        invoice_id="INVOICE_ID" if type == PledgeType.pay_on_completion else None,
    ).save(session=session)

    await session.commit()
    return pledge


@pytest_asyncio.fixture(scope="function")
async def pledge(
    session: AsyncSession,
    organization: Organization,
    repository: Repository,
    issue: Issue,
    pledging_organization: Organization,
) -> Pledge:
    return await create_pledge(
        session, organization, repository, issue, pledging_organization
    )


@pytest_asyncio.fixture(scope="function")
async def pledge_by_user(
    session: AsyncSession,
    organization: Organization,
    repository: Repository,
    issue: Issue,
) -> Pledge:
    user = await create_user(session)

    amount = secrets.randbelow(100000) + 1
    fee = round(amount * 0.05)
    pledge = await Pledge(
        id=uuid.uuid4(),
        issue_id=issue.id,
        repository_id=repository.id,
        organization_id=organization.id,
        by_user_id=user.id,
        amount=amount,
        fee=fee,
        state=PledgeState.created,
        type=PledgeType.pay_upfront,
    ).save(
        session=session,
    )

    await session.commit()
    return pledge


@pytest_asyncio.fixture(scope="function")
async def pull_request(
    session: AsyncSession,
    organization: Organization,
    repository: Repository,
) -> PullRequest:
    pr = await PullRequest(
        id=uuid.uuid4(),
        repository_id=repository.id,
        organization_id=organization.id,
        number=secrets.randbelow(5000),
        external_id=secrets.randbelow(5000),
        title="PR Title",
        author={
            "login": "pr_creator_login",
            "avatar_url": "http://example.com/avatar.jpg",
            "html_url": "https://github.com/pr_creator_login",
            "id": 47952,
        },
        platform=Platforms.github,
        state="open",
        issue_created_at=datetime.now(),
        issue_modified_at=datetime.now(),
        commits=1,
        additions=2,
        deletions=3,
        changed_files=4,
        is_draft=False,
        is_rebaseable=True,
        is_mergeable=True,
        is_merged=False,
        review_comments=5,
        maintainer_can_modify=True,
        merged_at=None,
        merge_commit_sha=None,
        body="x",
    ).save(
        session=session,
    )

    await session.commit()
    return pr


@pytest_asyncio.fixture(scope="function")
async def user_organization(
    session: AsyncSession,
    organization: Organization,
    user: User,
) -> UserOrganization:
    a = await UserOrganization(
        user_id=user.id,
        organization_id=organization.id,
    ).save(
        session=session,
    )

    await session.commit()
    return a


@pytest_asyncio.fixture(scope="function")
async def user_organization_admin(
    session: AsyncSession,
    organization: Organization,
    user: User,
) -> UserOrganization:
    a = await UserOrganization(
        user_id=user.id,
        organization_id=organization.id,
        is_admin=True,
    ).save(
        session=session,
    )

    await session.commit()
    return a


@pytest_asyncio.fixture(scope="function")
async def user_organization_second(
    session: AsyncSession,
    organization: Organization,
    user_second: User,
) -> UserOrganization:
    a = await UserOrganization(
        user_id=user_second.id,
        organization_id=organization.id,
    ).save(
        session=session,
    )

    await session.commit()
    return a


@pytest_asyncio.fixture
async def open_collective_account(session: AsyncSession, user: User) -> Account:
    account = Account(
        account_type=AccountType.open_collective,
        admin_id=user.id,
        open_collective_slug="polar",
        country="US",
        currency="USD",
        is_details_submitted=True,
        is_charges_enabled=True,
        is_payouts_enabled=True,
        business_type="fiscal_host",
    )
    await account.save(session)
    await session.commit()
    return account


async def create_subscription_tier(
    session: AsyncSession,
    *,
    type: SubscriptionTierType = SubscriptionTierType.individual,
    organization: Organization | None = None,
    repository: Repository | None = None,
    name: str = "Subscription Tier",
    price_amount: int = 1000,
    is_highlighted: bool = False,
    is_archived: bool = False,
) -> SubscriptionTier:
    assert (organization is not None) != (repository is not None)
    subscription_tier = SubscriptionTier(
        type=type,
        name=name,
        description="Description",
        price_amount=price_amount,
        price_currency="USD",
        is_highlighted=is_highlighted,
        is_archived=is_archived,
        organization_id=organization.id if organization is not None else None,
        repository_id=repository.id if repository is not None else None,
        stripe_product_id=rstr("PRODUCT_ID"),
        stripe_price_id=rstr("PRICE_ID"),
        subscription_tier_benefits=[],
    )
    session.add(subscription_tier)
    await session.commit()
    return subscription_tier


async def create_subscription_benefit(
    session: AsyncSession,
    *,
    type: SubscriptionBenefitType = SubscriptionBenefitType.custom,
    is_tax_applicable: bool | None = None,
    organization: Organization | None = None,
    repository: Repository | None = None,
    description: str = "Subscription Benefit",
    selectable: bool = True,
    deletable: bool = True,
    properties: dict[str, Any] = {"note": None},
) -> SubscriptionBenefit:
    assert (organization is not None) != (repository is not None)
    subscription_benefit = SubscriptionBenefit(
        type=type,
        description=description,
        is_tax_applicable=is_tax_applicable if is_tax_applicable is not None else False,
        organization_id=organization.id if organization is not None else None,
        repository_id=repository.id if repository is not None else None,
        selectable=selectable,
        deletable=deletable,
        properties=properties,
    )
    session.add(subscription_benefit)
    await session.commit()
    return subscription_benefit


async def add_subscription_benefits(
    session: AsyncSession,
    *,
    subscription_tier: SubscriptionTier,
    subscription_benefits: list[SubscriptionBenefit],
) -> SubscriptionTier:
    subscription_tier.subscription_tier_benefits = []
    for order, subscription_benefit in enumerate(subscription_benefits):
        benefit = SubscriptionTierBenefit(
            subscription_tier_id=subscription_tier.id,
            subscription_benefit_id=subscription_benefit.id,
            order=order,
        )

        subscription_tier.subscription_tier_benefits.append(benefit)
    session.add(subscription_tier)
    await session.commit()
    return subscription_tier


async def create_subscription(
    session: AsyncSession,
    *,
    subscription_tier: SubscriptionTier,
    user: User,
    organization: Organization | None = None,
    status: SubscriptionStatus = SubscriptionStatus.incomplete,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    stripe_subscription_id: str | None = "SUBSCRIPTION_ID",
) -> Subscription:
    now = datetime.now(UTC)
    subscription = Subscription(
        stripe_subscription_id=stripe_subscription_id,
        status=status,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        cancel_at_period_end=False,
        started_at=started_at,
        ended_at=ended_at,
        price_amount=subscription_tier.price_amount,
        price_currency=subscription_tier.price_currency,
        user_id=user.id,
        organization_id=organization.id if organization is not None else None,
        subscription_tier_id=subscription_tier.id,
    )
    session.add(subscription)
    await session.commit()
    return subscription


async def create_active_subscription(
    session: AsyncSession,
    *,
    subscription_tier: SubscriptionTier,
    user: User,
    organization: Organization | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    stripe_subscription_id: str | None = "SUBSCRIPTION_ID",
) -> Subscription:
    return await create_subscription(
        session,
        subscription_tier=subscription_tier,
        user=user,
        organization=organization,
        status=SubscriptionStatus.active,
        started_at=started_at or utc_now(),
        ended_at=ended_at,
        stripe_subscription_id=stripe_subscription_id,
    )


@pytest_asyncio.fixture
async def subscription_tier_organization_free(
    session: AsyncSession, organization: Organization
) -> SubscriptionTier:
    return await create_subscription_tier(
        session,
        type=SubscriptionTierType.free,
        price_amount=0,
        organization=organization,
    )


@pytest_asyncio.fixture
async def subscription_tier_organization(
    session: AsyncSession, organization: Organization
) -> SubscriptionTier:
    return await create_subscription_tier(session, organization=organization)


@pytest_asyncio.fixture
async def subscription_tier_organization_second(
    session: AsyncSession, organization: Organization
) -> SubscriptionTier:
    return await create_subscription_tier(session, organization=organization)


@pytest_asyncio.fixture
async def subscription_tier_repository(
    session: AsyncSession, public_repository: Repository
) -> SubscriptionTier:
    return await create_subscription_tier(session, repository=public_repository)


@pytest_asyncio.fixture
async def subscription_tier_private_repository(
    session: AsyncSession, repository: Repository
) -> SubscriptionTier:
    return await create_subscription_tier(
        session, type=SubscriptionTierType.business, repository=repository
    )


@pytest_asyncio.fixture
async def subscription_tiers(
    subscription_tier_organization: SubscriptionTier,
    subscription_tier_organization_second: SubscriptionTier,
    subscription_tier_organization_free: SubscriptionTier,
    subscription_tier_repository: SubscriptionTier,
    subscription_tier_private_repository: SubscriptionTier,
) -> list[SubscriptionTier]:
    return [
        subscription_tier_organization_free,
        subscription_tier_organization,
        subscription_tier_organization_second,
        subscription_tier_repository,
        subscription_tier_private_repository,
    ]


@pytest_asyncio.fixture
async def subscription_benefit_organization(
    session: AsyncSession, organization: Organization
) -> SubscriptionBenefit:
    return await create_subscription_benefit(session, organization=organization)


@pytest_asyncio.fixture
async def subscription_benefit_repository(
    session: AsyncSession, public_repository: Repository
) -> SubscriptionBenefit:
    return await create_subscription_benefit(session, repository=public_repository)


@pytest_asyncio.fixture
async def subscription_benefit_private_repository(
    session: AsyncSession, repository: Repository
) -> SubscriptionBenefit:
    return await create_subscription_benefit(
        session, type=SubscriptionBenefitType.custom, repository=repository
    )


@pytest_asyncio.fixture
async def subscription_benefits(
    subscription_benefit_organization: SubscriptionBenefit,
    subscription_benefit_repository: SubscriptionBenefit,
    subscription_benefit_private_repository: SubscriptionBenefit,
) -> list[SubscriptionBenefit]:
    return [
        subscription_benefit_organization,
        subscription_benefit_repository,
        subscription_benefit_private_repository,
    ]


@pytest_asyncio.fixture
async def organization_account(
    session: AsyncSession, organization: Organization, user: User
) -> Account:
    account = Account(
        account_type=AccountType.stripe,
        admin_id=user.id,
        country="US",
        currency="USD",
        is_details_submitted=True,
        is_charges_enabled=True,
        is_payouts_enabled=True,
        stripe_id="STRIPE_ACCOUNT_ID",
    )
    session.add(account)
    organization.account = account
    session.add(organization)
    await session.commit()
    return account


@pytest_asyncio.fixture
async def organization_subscriber(session: AsyncSession) -> Organization:
    return await create_organization(session)


@pytest_asyncio.fixture
async def organization_subscriber_admin(
    session: AsyncSession, organization_subscriber: Organization, user_second: User
) -> User:
    user_organization = UserOrganization(
        user_id=user_second.id,
        organization_id=organization_subscriber.id,
        is_admin=True,
    )
    session.add(user_organization)
    await session.commit()
    return user_second


@pytest_asyncio.fixture
async def organization_subscriber_members(
    session: AsyncSession, organization_subscriber: Organization
) -> list[User]:
    users: list[User] = []
    for _ in range(5):
        user = await create_user(session)
        user_organization = UserOrganization(
            user_id=user.id,
            organization_id=organization_subscriber.id,
            is_admin=False,
        )
        session.add(user_organization)
        users.append(user)
    await session.commit()
    return users


@pytest_asyncio.fixture
async def subscription(
    session: AsyncSession, subscription_tier_organization: SubscriptionTier, user: User
) -> Subscription:
    return await create_subscription(
        session, subscription_tier=subscription_tier_organization, user=user
    )


@pytest_asyncio.fixture
async def subscription_organization(
    session: AsyncSession,
    subscription_tier_organization: SubscriptionTier,
    organization_subscriber: Organization,
    user_second: User,
) -> Subscription:
    return await create_subscription(
        session,
        subscription_tier=subscription_tier_organization,
        user=user_second,
        organization=organization_subscriber,
    )


async def create_subscription_benefit_grant(
    session: AsyncSession,
    user: User,
    subscription: Subscription,
    subscription_benefit: SubscriptionBenefit,
) -> SubscriptionBenefitGrant:
    grant = SubscriptionBenefitGrant(
        subscription=subscription,
        subscription_benefit=subscription_benefit,
        user=user,
    )
    session.add(grant)
    await session.commit()
    return grant


@pytest_asyncio.fixture(scope="function")
async def article(
    session: AsyncSession,
    organization: Organization,
    user: User,
) -> Article:
    article = await Article(
        id=uuid.uuid4(),
        organization_id=organization.id,
        slug="test",
        title="test",
        body="test!",
        created_by=user.id,
    ).save(session=session)

    await session.commit()
    return article
