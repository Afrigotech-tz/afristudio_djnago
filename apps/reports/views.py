"""
reports/views.py
Admin-only report endpoints for auctions, artworks, and sales.
All views support optional date filtering via ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
"""

from datetime import datetime, date
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated


def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, '%Y-%m-%d').date()
    except ValueError:
        return None


def _date_filter(qs, field, start, end):
    if start:
        qs = qs.filter(**{f'{field}__date__gte': start})
    if end:
        qs = qs.filter(**{f'{field}__date__lte': end})
    return qs


class AuctionsReportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from apps.auctions.models import Auction

        start = _parse_date(request.query_params.get('start_date'))
        end   = _parse_date(request.query_params.get('end_date'))
        status_filter = request.query_params.get('status')

        qs = Auction.objects.select_related('artwork', 'created_by', 'winner')
        qs = _date_filter(qs, 'created_at', start, end)
        if status_filter:
            qs = qs.filter(status=status_filter)

        summary = qs.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            live=Count('id', filter=Q(status='live')),
            ended=Count('id', filter=Q(status='ended')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            total_bids=Sum('total_bids'),
            total_revenue=Sum('current_price', filter=Q(status='ended', winner__isnull=False)),
        )

        records = []
        for a in qs.order_by('-created_at'):
            records.append({
                'uuid': str(a.uuid),
                'artwork': a.artwork.name,
                'artwork_image': request.build_absolute_uri(a.artwork.image.url) if a.artwork.image else None,
                'status': a.status,
                'currency': a.currency,
                'start_price': str(a.start_price),
                'reserve_price': str(a.reserve_price) if a.reserve_price else None,
                'current_price': str(a.current_price) if a.current_price else None,
                'total_bids': a.total_bids,
                'start_time': a.start_time.isoformat(),
                'end_time': a.end_time.isoformat(),
                'created_by': a.created_by.name if a.created_by else None,
                'winner': a.winner.name if a.winner else None,
                'created_at': a.created_at.date().isoformat(),
            })

        return Response({
            'report': 'auctions',
            'generated_at': timezone.now().isoformat(),
            'filters': {'start_date': str(start) if start else None, 'end_date': str(end) if end else None, 'status': status_filter},
            'summary': {
                'total': summary['total'] or 0,
                'pending': summary['pending'] or 0,
                'live': summary['live'] or 0,
                'ended': summary['ended'] or 0,
                'cancelled': summary['cancelled'] or 0,
                'total_bids': summary['total_bids'] or 0,
                'total_revenue': str(summary['total_revenue'] or 0),
            },
            'data': records,
        })


class SoldArtworksReportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from apps.artworks.models import Artwork
        from apps.orders.models import OrderItem

        start = _parse_date(request.query_params.get('start_date'))
        end   = _parse_date(request.query_params.get('end_date'))

        qs = Artwork.objects.filter(is_sold=True).select_related('category')
        qs = _date_filter(qs, 'updated_at', start, end)

        records = []
        for artwork in qs.order_by('-updated_at'):
            item = (
                OrderItem.objects
                .filter(artwork=artwork)
                .select_related('order', 'order__user')
                .order_by('-created_at')
                .first()
            )
            records.append({
                'uuid': str(artwork.uuid),
                'name': artwork.name,
                'category': artwork.category.name,
                'dimensions': artwork.dimensions,
                'base_price': str(artwork.base_price),
                'base_currency': artwork.base_currency,
                'image': request.build_absolute_uri(artwork.image.url) if artwork.image else None,
                'sold_at': artwork.updated_at.date().isoformat(),
                'sold_for': str(item.price) if item else str(artwork.base_price),
                'sold_currency': item.currency if item else artwork.base_currency,
                'buyer': item.order.user.name if item and item.order else None,
                'order_id': item.order.id if item and item.order else None,
                'via_auction': item.auction_id is not None if item else False,
            })

        total_revenue_by_currency: dict = {}
        for r in records:
            cur = r['sold_currency']
            total_revenue_by_currency[cur] = total_revenue_by_currency.get(cur, 0) + float(r['sold_for'])

        return Response({
            'report': 'sold_artworks',
            'generated_at': timezone.now().isoformat(),
            'filters': {'start_date': str(start) if start else None, 'end_date': str(end) if end else None},
            'summary': {
                'total_sold': len(records),
                'revenue_by_currency': {k: str(round(v, 2)) for k, v in total_revenue_by_currency.items()},
                'via_auction': sum(1 for r in records if r['via_auction']),
                'direct_sale': sum(1 for r in records if not r['via_auction']),
            },
            'data': records,
        })


class AvailableArtworksReportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from apps.artworks.models import Artwork

        start = _parse_date(request.query_params.get('start_date'))
        end   = _parse_date(request.query_params.get('end_date'))
        category = request.query_params.get('category')

        qs = Artwork.objects.filter(is_sold=False).select_related('category')
        qs = _date_filter(qs, 'created_at', start, end)
        if category:
            qs = qs.filter(category__slug=category)

        records = []
        for artwork in qs.order_by('-created_at'):
            has_auction = hasattr(artwork, 'auction')
            auction_status = None
            if has_auction:
                try:
                    auction_status = artwork.auction.status
                except Exception:
                    has_auction = False
            records.append({
                'uuid': str(artwork.uuid),
                'name': artwork.name,
                'category': artwork.category.name,
                'dimensions': artwork.dimensions,
                'base_price': str(artwork.base_price),
                'base_currency': artwork.base_currency,
                'image': request.build_absolute_uri(artwork.image.url) if artwork.image else None,
                'has_auction': has_auction,
                'auction_status': auction_status,
                'created_at': artwork.created_at.date().isoformat(),
            })

        value_by_currency: dict = {}
        for r in records:
            cur = r['base_currency']
            value_by_currency[cur] = value_by_currency.get(cur, 0) + float(r['base_price'])

        return Response({
            'report': 'available_artworks',
            'generated_at': timezone.now().isoformat(),
            'filters': {'start_date': str(start) if start else None, 'end_date': str(end) if end else None, 'category': category},
            'summary': {
                'total_available': len(records),
                'with_auction': sum(1 for r in records if r['has_auction']),
                'without_auction': sum(1 for r in records if not r['has_auction']),
                'estimated_value_by_currency': {k: str(round(v, 2)) for k, v in value_by_currency.items()},
            },
            'data': records,
        })


class SalesReportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from apps.orders.models import Order, OrderItem

        start = _parse_date(request.query_params.get('start_date'))
        end   = _parse_date(request.query_params.get('end_date'))
        status_filter = request.query_params.get('status')

        qs = Order.objects.select_related('user', 'auction__artwork')
        qs = _date_filter(qs, 'created_at', start, end)
        if status_filter:
            qs = qs.filter(status=status_filter)

        summary = qs.aggregate(
            total_orders=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            confirmed=Count('id', filter=Q(status='confirmed')),
            shipped=Count('id', filter=Q(status='shipped')),
            delivered=Count('id', filter=Q(status='delivered')),
            cancelled=Count('id', filter=Q(status='cancelled')),
        )

        revenue_by_currency: dict = {}
        orders_data = list(qs.order_by('-created_at').prefetch_related('items'))
        for o in orders_data:
            if o.status not in ('pending', 'cancelled'):
                cur = o.currency
                revenue_by_currency[cur] = revenue_by_currency.get(cur, 0) + float(o.total)

        records = []
        for o in orders_data:
            items = [
                {
                    'artwork_name': i.artwork_name,
                    'price': str(i.price),
                    'currency': i.currency,
                    'via_auction': i.auction_id is not None,
                }
                for i in o.items.all()
            ]
            records.append({
                'id': o.id,
                'uuid': str(o.uuid),
                'buyer': o.user.name,
                'buyer_email': o.user.email or '',
                'status': o.status,
                'total': str(o.total),
                'currency': o.currency,
                'delivery_city': o.delivery_city,
                'delivery_country': o.delivery_country,
                'via_auction': o.auction_id is not None,
                'items': items,
                'created_at': o.created_at.date().isoformat(),
            })

        return Response({
            'report': 'sales',
            'generated_at': timezone.now().isoformat(),
            'filters': {'start_date': str(start) if start else None, 'end_date': str(end) if end else None, 'status': status_filter},
            'summary': {
                'total_orders': summary['total_orders'] or 0,
                'pending': summary['pending'] or 0,
                'confirmed': summary['confirmed'] or 0,
                'shipped': summary['shipped'] or 0,
                'delivered': summary['delivered'] or 0,
                'cancelled': summary['cancelled'] or 0,
                'revenue_by_currency': {k: str(round(v, 2)) for k, v in revenue_by_currency.items()},
            },
            'data': records,
        })
