from django.contrib.gis import admin
from .models import StopScreen, StationScreen, VehicleScreen

# Register your models here.

admin.site.register(StopScreen, admin.GISModelAdmin)
admin.site.register(StationScreen, admin.GISModelAdmin)
admin.site.register(VehicleScreen)
