from django.contrib.gis import admin
from .models import Weather, CommonAlert, Social

# Register your models here.

admin.site.register(Weather)
admin.site.register(CommonAlert)
admin.site.register(Social)
