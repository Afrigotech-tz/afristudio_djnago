from django.contrib import admin
from .models import Auction, Bid


class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    readonly_fields = ('uuid', 'bidder', 'amount', 'is_winning', 'created_at')
    can_delete = False
    ordering = ('-amount',)


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = ('artwork', 'status', 'current_price', 'currency', 'total_bids', 'winner', 'start_time', 'end_time')
    list_filter = ('status', 'currency')
    search_fields = ('artwork__name', 'winner__email')
    readonly_fields = ('uuid', 'total_bids', 'current_price', 'winner', 'created_at', 'updated_at')
    inlines = [BidInline]
    actions = ['start_auctions', 'end_auctions']

    def start_auctions(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status=Auction.STATUS_PENDING).update(
            status=Auction.STATUS_LIVE, start_time=timezone.now()
        )
        self.message_user(request, f'{updated} auction(s) started.')
    start_auctions.short_description = 'Start selected auctions'

    def end_auctions(self, request, queryset):
        from .models import close_auction
        for auction in queryset.filter(status=Auction.STATUS_LIVE):
            close_auction(auction)
        self.message_user(request, 'Selected live auctions have been ended.')
    end_auctions.short_description = 'End selected live auctions'


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('auction', 'bidder', 'amount', 'is_winning', 'created_at')
    list_filter = ('is_winning',)
    search_fields = ('bidder__email', 'auction__artwork__name')
