from rest_framework import serializers
from .models import Currency


class CurrencySerializer(serializers.ModelSerializer):
    """Equivalent to CurrencyResource."""
    rate = serializers.DecimalField(source='exchange_rate', max_digits=15, decimal_places=8, read_only=True)

    class Meta:
        model = Currency
        fields = ['uuid', 'code', 'symbol', 'rate']
        read_only_fields = ['uuid', 'rate']


class StoreCurrencySerializer(serializers.ModelSerializer):
    """Equivalent to StoreCurrencyRequest + UpdateCurrencyRequest."""
    class Meta:
        model = Currency
        fields = ['code', 'symbol', 'exchange_rate']

    def validate_code(self, value):
        qs = Currency.objects.filter(code=value.upper())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Currency code already exists.')
        return value.upper()
