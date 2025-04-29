from django.contrib.gis import admin
from unfold.admin import ModelAdmin
from django.contrib.gis.db import models
from django.contrib.gis.forms import OSMWidget


class GeoModelAdminMixin:
    gis_widget = OSMWidget
    gis_widget_kwargs = {}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.GeometryField) and (
            db_field.dim < 3 or self.gis_widget.supports_3d
        ):
            kwargs["widget"] = self.gis_widget(**self.gis_widget_kwargs)
            return db_field.formfield(**kwargs)
        else:
            return super().formfield_for_dbfield(db_field, request, **kwargs)


class GeoModelAdmin(GeoModelAdminMixin, ModelAdmin):
    pass


from .models import *

# Register your models here.


@admin.register(FeedMessage)
class FeedMessageAdmin(ModelAdmin):
    pass


@admin.register(Stop)
class StopAdmin(GeoModelAdmin):
    exclude = ["stop_lat", "stop_lon"]


@admin.register(GeoShape)
class GeoShapeAdmin(GeoModelAdmin):
    pass


@admin.register(VehiclePosition)
class VehiclePositionAdmin(GeoModelAdmin):
    pass


@admin.register(GTFSProvider)
class GTFSProviderAdmin(ModelAdmin):
    pass


@admin.register(Feed)
class FeedAdmin(ModelAdmin):
    pass


@admin.register(Agency)
class AgencyAdmin(ModelAdmin):
    pass


@admin.register(Route)
class RouteAdmin(ModelAdmin):
    pass


@admin.register(Calendar)
class CalendarAdmin(ModelAdmin):
    pass


@admin.register(CalendarDate)
class CalendarDateAdmin(ModelAdmin):
    pass


@admin.register(Shape)
class ShapeAdmin(ModelAdmin):
    pass


@admin.register(Trip)
class TripAdmin(ModelAdmin):
    pass


@admin.register(StopTime)
class StopTimeAdmin(ModelAdmin):
    pass


@admin.register(FareAttribute)
class FareAttributeAdmin(ModelAdmin):
    pass


@admin.register(FareRule)
class FareRuleAdmin(ModelAdmin):
    pass


@admin.register(FeedInfo)
class FeedInfoAdmin(ModelAdmin):
    pass


@admin.register(RouteStop)
class RouteStopAdmin(ModelAdmin):
    pass


@admin.register(TripDuration)
class TripDurationAdmin(ModelAdmin):
    pass


@admin.register(TripTime)
class TripTimeAdmin(ModelAdmin):
    pass


@admin.register(TripUpdate)
class TripUpdateAdmin(ModelAdmin):
    pass


@admin.register(StopTimeUpdate)
class StopTimeUpdateAdmin(ModelAdmin):
    pass
