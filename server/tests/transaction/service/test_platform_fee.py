from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from polar.enums import AccountType
from polar.models import (
    Account,
    IssueReward,
    Organization,
    Pledge,
    Subscription,
    Transaction,
    User,
)
from polar.models.transaction import PaymentProcessor, PlatformFeeType, TransactionType
from polar.postgres import AsyncSession
from polar.transaction.service.platform_fee import (
    DanglingBalanceTransactions,
    PayoutAmountTooLow,
)
from polar.transaction.service.platform_fee import (
    platform_fee_transaction as platform_fee_transaction_service,
)
from tests.transaction.conftest import create_account


async def create_balance_transactions(
    session: AsyncSession,
    *,
    account: Account,
    pledge: Pledge | None = None,
    issue_reward: IssueReward | None = None,
    subscription: Subscription | None = None,
) -> tuple[Transaction, Transaction]:
    payment_transaction = Transaction(
        type=TransactionType.payment,
        processor=PaymentProcessor.stripe,
        currency="usd",
        amount=10000,
        account_currency="usd",
        account_amount=10000,
        tax_amount=0,
        pledge=pledge,
        issue_reward=issue_reward,
        subscription=subscription,
    )
    session.add(payment_transaction)

    payment_transaction_fee = Transaction(
        type=TransactionType.processor_fee,
        processor=PaymentProcessor.stripe,
        currency="usd",
        amount=-500,
        account_currency="usd",
        account_amount=-500,
        tax_amount=0,
        incurred_by_transaction=payment_transaction,
    )
    session.add(payment_transaction_fee)

    outgoing = Transaction(
        type=TransactionType.balance,
        processor=None,
        currency="usd",
        amount=-10000,
        account_currency="usd",
        account_amount=-10000,
        tax_amount=0,
        pledge=pledge,
        issue_reward=issue_reward,
        subscription=subscription,
        balance_correlation_key="BALANCE_1",
        payment_transaction=payment_transaction,
    )
    incoming = Transaction(
        type=TransactionType.balance,
        processor=None,
        currency="usd",
        amount=10000,
        account_currency="usd",
        account_amount=10000,
        account=account,
        tax_amount=0,
        pledge=pledge,
        issue_reward=issue_reward,
        subscription=subscription,
        balance_correlation_key="BALANCE_1",
        payment_transaction=payment_transaction,
    )
    session.add(outgoing)
    session.add(incoming)
    await session.commit()
    return outgoing, incoming


@pytest_asyncio.fixture
async def account_processor_fees(
    session: AsyncSession, organization: Organization, user: User
) -> Account:
    return await create_account(
        session, organization, user, processor_fees_applicable=True
    )


@pytest.mark.asyncio
class TestCreateFeesReversalBalances:
    async def test_dangling_balance_transactions(
        self, session: AsyncSession, account_processor_fees: Account
    ) -> None:
        # then
        session.expunge_all()

        balance_transactions = await create_balance_transactions(
            session, account=account_processor_fees
        )

        with pytest.raises(DanglingBalanceTransactions):
            await platform_fee_transaction_service.create_fees_reversal_balances(
                session, balance_transactions=balance_transactions
            )

    async def test_pledge(
        self,
        session: AsyncSession,
        account_processor_fees: Account,
        transaction_pledge: Pledge,
        transaction_issue_reward: IssueReward,
    ) -> None:
        # then
        session.expunge_all()

        balance_transactions = await create_balance_transactions(
            session,
            account=account_processor_fees,
            pledge=transaction_pledge,
            issue_reward=transaction_issue_reward,
        )
        outgoing, incoming = balance_transactions

        fees_reversal_balances = (
            await platform_fee_transaction_service.create_fees_reversal_balances(
                session, balance_transactions=balance_transactions
            )
        )

        assert len(fees_reversal_balances) == 3

        # Platform fee
        reversal_outgoing, reversal_incoming = fees_reversal_balances[0]

        assert reversal_outgoing.amount == -500
        assert reversal_outgoing.account_id == incoming.account_id
        assert reversal_outgoing.platform_fee_type == PlatformFeeType.platform
        assert reversal_outgoing.incurred_by_transaction == incoming

        assert reversal_incoming.amount == 500
        assert reversal_incoming.account_id is None
        assert reversal_incoming.platform_fee_type == PlatformFeeType.platform
        assert reversal_incoming.incurred_by_transaction == outgoing

        # Payment fee
        reversal_outgoing, reversal_incoming = fees_reversal_balances[1]

        assert reversal_outgoing.amount == -500
        assert reversal_outgoing.account_id == incoming.account_id
        assert reversal_outgoing.platform_fee_type == PlatformFeeType.payment
        assert reversal_outgoing.incurred_by_transaction == incoming

        assert reversal_incoming.amount == 500
        assert reversal_incoming.account_id is None
        assert reversal_incoming.platform_fee_type == PlatformFeeType.payment
        assert reversal_incoming.incurred_by_transaction == outgoing

        # Invoice fee
        reversal_outgoing, reversal_incoming = fees_reversal_balances[2]

        assert reversal_outgoing.amount == -50
        assert reversal_outgoing.account_id == incoming.account_id
        assert reversal_outgoing.platform_fee_type == PlatformFeeType.invoice
        assert reversal_outgoing.incurred_by_transaction == incoming

        assert reversal_incoming.amount == 50
        assert reversal_incoming.account_id is None
        assert reversal_incoming.platform_fee_type == PlatformFeeType.invoice
        assert reversal_incoming.incurred_by_transaction == outgoing

    async def test_subscription(
        self,
        session: AsyncSession,
        account_processor_fees: Account,
        transaction_subscription: Subscription,
    ) -> None:
        # then
        session.expunge_all()

        balance_transactions = await create_balance_transactions(
            session,
            account=account_processor_fees,
            subscription=transaction_subscription,
        )
        outgoing, incoming = balance_transactions

        fees_reversal_balances = (
            await platform_fee_transaction_service.create_fees_reversal_balances(
                session, balance_transactions=balance_transactions
            )
        )

        assert len(fees_reversal_balances) == 3

        reversal_outgoing, reversal_incoming = fees_reversal_balances[0]

        assert reversal_outgoing.amount == -500
        assert reversal_outgoing.account_id == incoming.account_id
        assert reversal_outgoing.platform_fee_type == PlatformFeeType.platform
        assert reversal_outgoing.incurred_by_transaction == incoming

        assert reversal_incoming.amount == 500
        assert reversal_incoming.account_id is None
        assert reversal_incoming.platform_fee_type == PlatformFeeType.platform
        assert reversal_incoming.incurred_by_transaction == outgoing

        # Payment fee
        reversal_outgoing, reversal_incoming = fees_reversal_balances[1]

        assert reversal_outgoing.amount == -500
        assert reversal_outgoing.account_id == incoming.account_id
        assert reversal_outgoing.platform_fee_type == PlatformFeeType.payment
        assert reversal_outgoing.incurred_by_transaction == incoming

        assert reversal_incoming.amount == 500
        assert reversal_incoming.account_id is None
        assert reversal_incoming.platform_fee_type == PlatformFeeType.payment
        assert reversal_incoming.incurred_by_transaction == outgoing

        # Subscription fee
        reversal_outgoing, reversal_incoming = fees_reversal_balances[2]

        assert reversal_outgoing.amount == -50
        assert reversal_outgoing.account_id == incoming.account_id
        assert reversal_outgoing.platform_fee_type == PlatformFeeType.subscription
        assert reversal_outgoing.incurred_by_transaction == incoming

        assert reversal_incoming.amount == 50
        assert reversal_incoming.account_id is None
        assert reversal_incoming.platform_fee_type == PlatformFeeType.subscription
        assert reversal_incoming.incurred_by_transaction == outgoing


@pytest.mark.asyncio
class TestCreatePayoutFeesBalances:
    async def test_not_processor_fees_applicable(
        self, session: AsyncSession, account: Account
    ) -> None:
        # then
        session.expunge_all()

        (
            balance_amount,
            payout_fees_balances,
        ) = await platform_fee_transaction_service.create_payout_fees_balances(
            session, account=account, balance_amount=10000
        )

        assert balance_amount == 10000
        assert payout_fees_balances == []

    async def test_not_stripe(
        self, session: AsyncSession, organization: Organization, user: User
    ) -> None:
        account = await create_account(
            session,
            organization=organization,
            user=user,
            account_type=AccountType.open_collective,
        )

        # then
        session.expunge_all()

        (
            balance_amount,
            payout_fees_balances,
        ) = await platform_fee_transaction_service.create_payout_fees_balances(
            session, account=account, balance_amount=10000
        )

        assert balance_amount == 10000
        assert payout_fees_balances == []

    async def test_stripe_amount_too_low(
        self, session: AsyncSession, account_processor_fees: Account
    ) -> None:
        # then
        session.expunge_all()

        with pytest.raises(PayoutAmountTooLow):
            await platform_fee_transaction_service.create_payout_fees_balances(
                session, account=account_processor_fees, balance_amount=1
            )

    @pytest.mark.parametrize(
        "payout_created_at", [None, datetime.now(UTC) - timedelta(days=31)]
    )
    async def test_stripe_no_last_payout(
        self,
        payout_created_at: datetime | None,
        session: AsyncSession,
        account_processor_fees: Account,
    ) -> None:
        if payout_created_at is not None:
            payout_transaction = Transaction(
                created_at=payout_created_at,
                type=TransactionType.payout,
                processor=PaymentProcessor.stripe,
                currency="usd",
                amount=-10000,
                account_currency="usd",
                account_amount=-10000,
                account=account_processor_fees,
                tax_amount=0,
            )
            session.add(payout_transaction)
            await session.commit()

        # then
        session.expunge_all()

        (
            balance_amount,
            payout_fees_balances,
        ) = await platform_fee_transaction_service.create_payout_fees_balances(
            session, account=account_processor_fees, balance_amount=10000
        )

        assert len(payout_fees_balances) == 2

        account_fee_outgoing = payout_fees_balances[0][0]
        assert account_fee_outgoing.platform_fee_type == PlatformFeeType.account
        assert account_fee_outgoing.account_id == account_processor_fees.id

        payout_fee_outgoing = payout_fees_balances[1][0]
        assert payout_fee_outgoing.platform_fee_type == PlatformFeeType.payout
        assert payout_fee_outgoing.account_id == account_processor_fees.id

        assert (
            balance_amount
            == 10000 + account_fee_outgoing.amount + payout_fee_outgoing.amount
        )

    async def test_stripe_last_payout(
        self, session: AsyncSession, account_processor_fees: Account
    ) -> None:
        payout_transaction = Transaction(
            created_at=datetime.now(UTC) - timedelta(days=7),
            type=TransactionType.payout,
            processor=PaymentProcessor.stripe,
            currency="usd",
            amount=-10000,
            account_currency="usd",
            account_amount=-10000,
            account=account_processor_fees,
            tax_amount=0,
        )
        session.add(payout_transaction)
        await session.commit()

        # then
        session.expunge_all()

        (
            balance_amount,
            payout_fees_balances,
        ) = await platform_fee_transaction_service.create_payout_fees_balances(
            session, account=account_processor_fees, balance_amount=10000
        )

        assert len(payout_fees_balances) == 1

        payout_fee_outgoing = payout_fees_balances[0][0]
        assert payout_fee_outgoing.platform_fee_type == PlatformFeeType.payout
        assert payout_fee_outgoing.account_id == account_processor_fees.id

        assert balance_amount == 10000 + payout_fee_outgoing.amount

    async def test_stripe_cross_border(
        self, session: AsyncSession, organization: Organization, user: User
    ) -> None:
        account = await create_account(
            session,
            organization,
            user,
            country="FR",
            currency="eur",
            processor_fees_applicable=True,
        )

        # then
        session.expunge_all()

        (
            balance_amount,
            payout_fees_balances,
        ) = await platform_fee_transaction_service.create_payout_fees_balances(
            session, account=account, balance_amount=10000
        )

        assert len(payout_fees_balances) == 3

        account_fee_outgoing = payout_fees_balances[0][0]
        assert account_fee_outgoing.platform_fee_type == PlatformFeeType.account
        assert account_fee_outgoing.account_id == account.id

        cross_border_fee_outgoing = payout_fees_balances[1][0]
        assert (
            cross_border_fee_outgoing.platform_fee_type
            == PlatformFeeType.cross_border_transfer
        )
        assert cross_border_fee_outgoing.account_id == account.id

        payout_fee_outgoing = payout_fees_balances[2][0]
        assert payout_fee_outgoing.platform_fee_type == PlatformFeeType.payout
        assert payout_fee_outgoing.account_id == account.id

        assert (
            balance_amount
            == 10000
            + account_fee_outgoing.amount
            + cross_border_fee_outgoing.amount
            + payout_fee_outgoing.amount
        )
