from django.db import models


class GeocodedAddress(models.Model):
    raw_address = models.CharField(
        'Исходный адрес',
        max_length=255,
        unique=True,
    )
    lat = models.FloatField('Широта', null=True, blank=True)
    lng = models.FloatField('Долгота', null=True, blank=True)
    provider = models.CharField(
        'Провайдер',
        max_length=50,
        default='yandex',
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Геокодированный адрес'
        verbose_name_plural = 'Геокодированные адреса'

    def __str__(self):
        return self.raw_address
