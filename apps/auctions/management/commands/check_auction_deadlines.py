"""
management command: check_auction_deadlines

Run periodically (e.g. every 15 minutes via cron / Celery beat) to:
  1. Find AuctionWinner records that are pending and past their deadline.
  2. Mark them as expired.
  3. Create an AuctionPaymentViolation for the user.
  4. Relist the auction if config.relist_on_expired is True.
  5. Notify the user that their auction win has been forfeited.

Usage:
    python manage.py check_auction_deadlines
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.auctions.models import AuctionConfig, AuctionWinner, AuctionPaymentViolation, relist_auction


class Command(BaseCommand):
    help = 'Expire overdue auction payment deadlines, create violations, and relist auctions.'

    def handle(self, *args, **options):
        config = AuctionConfig.get_config()
        now    = timezone.now()

        overdue = AuctionWinner.objects.filter(
            payment_status=AuctionWinner.PAYMENT_PENDING,
            payment_deadline__lt=now,
        ).select_related('user', 'auction', 'auction__artwork')

        count = 0
        for winner_rec in overdue:
            # Mark expired
            winner_rec.payment_status = AuctionWinner.PAYMENT_EXPIRED
            winner_rec.save(update_fields=['payment_status'])

            # Create violation (skip if already exists)
            violation, created = AuctionPaymentViolation.objects.get_or_create(
                auction_winner=winner_rec,
                defaults={'user': winner_rec.user},
            )

            if created:
                self.stdout.write(
                    f'  Violation recorded: {winner_rec.user} — '
                    f'"{winner_rec.auction.artwork.name}"'
                )
                # Auto-apply bidding ban when threshold is reached
                total_violations = AuctionPaymentViolation.objects.filter(
                    user=winner_rec.user
                ).count()
                if total_violations >= config.max_violations:
                    ban_until = now + timedelta(days=config.ban_duration_days)
                    winner_rec.user.bidding_banned_until = ban_until
                    winner_rec.user.save(update_fields=['bidding_banned_until'])
                    self.stdout.write(
                        f'  Bidding banned: {winner_rec.user} until '
                        f'{ban_until.strftime("%Y-%m-%d %H:%M UTC")}'
                    )

            # Relist if configured
            if config.relist_on_expired:
                auction = winner_rec.auction
                relist_auction(auction, config)
                self.stdout.write(
                    f'  Auction relisted: "{auction.artwork.name}" '
                    f'(new end: {auction.end_time.strftime("%Y-%m-%d %H:%M UTC")})'
                )

            # Notify user
            try:
                from apps.notifications.tasks import notify_async
                total_violations = AuctionPaymentViolation.objects.filter(
                    user=winner_rec.user
                ).count()
                suspended = total_violations >= config.max_violations
                notify_async(
                    user_id=winner_rec.user.pk,
                    subject=f'Auction win forfeited — "{winner_rec.auction.artwork.name}"',
                    message=(
                        f'Hi {winner_rec.user.name}, your auction win for '
                        f'"{winner_rec.auction.artwork.name}" has been forfeited because '
                        f'payment was not completed within the deadline. '
                        f'This is violation #{total_violations}. '
                        + (
                            f'Your bidding privileges have been suspended. '
                            f'Please contact support.'
                            if suspended else
                            f'You have {config.max_violations - total_violations} '
                            f'violation(s) remaining before your account is suspended.'
                        )
                    ),
                    template='emails/auction_win_forfeited.html',
                    context={
                        'name': winner_rec.user.name,
                        'artwork_name': winner_rec.auction.artwork.name,
                        'total_violations': total_violations,
                        'max_violations': config.max_violations,
                        'suspended': suspended,
                    },
                )
            except Exception as exc:
                self.stderr.write(f'  Notification failed for {winner_rec.user}: {exc}')

            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'check_auction_deadlines: processed {count} overdue winner record(s).'
            )
        )
