from django.contrib.gis.db import models
from feed.models import Stop

# Create your models here.


class Vehicle(models.Model):
    """Vehicles that are used for public transit.
    Maps to vehicles.txt in the GTFS feed.
    """

    vehicle_id = models.CharField(
        max_length=255, primary_key=True, help_text="Identificador único del vehículo."
    )
    vehicle_label = models.CharField(
        max_length=255, blank=True, null=True, help_text="Etiqueta del vehículo."
    )
    vehicle_license_plate = models.CharField(
        max_length=255, blank=True, null=True, help_text="Placa del vehículo."
    )
    vehicle_model = models.CharField(
        max_length=255, blank=True, null=True, help_text="Modelo del vehículo."
    )
    vehicle_make = models.CharField(
        max_length=255, blank=True, null=True, help_text="Marca del vehículo."
    )
    vehicle_year = models.PositiveIntegerField(
        blank=True, null=True, help_text="Año del vehículo."
    )
    vehicle_url = models.URLField(blank=True, null=True, help_text="URL del vehículo.")
    wheelchair_accessible = models.PositiveIntegerField(
        blank=True, null=True, help_text="Acceso para sillas de ruedas."
    )

    def __str__(self):
        return self.vehicle_label


class Screen(models.Model):
    ORIENTATION_CHOICES = [
        ("landscape", "Horizontal"),
        ("portrait", "Vertical"),
    ]
    RATIO_CHOICES = [
        ("4:3", "4:3"),
        ("16:9", "16:9"),
        ("16:10", "16:10"),
    ]

    screen_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    location = models.PointField(geography=True, blank=True, null=True)
    orientation = models.CharField(
        max_length=10,
        choices=ORIENTATION_CHOICES,
        default="landscape",
        blank=True,
        null=True,
    )
    ratio = models.CharField(
        max_length=10, choices=RATIO_CHOICES, default="16:9", blank=True, null=True
    )
    size = models.PositiveIntegerField(
        help_text="diagonal in inches", blank=True, null=True
    )
    has_audio = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        abstract = True


class StopScreen(Screen):
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE)
    stop_slug = models.SlugField(unique=True)
    # TODO: fields for heading and for screen layout

    def __str__(self):
        if self.stop.stop_heading:
            return (
                f"{self.stop.stop_name} ({self.stop.stop_heading}) ({self.screen_id})"
            )
        else:
            return f"{self.stop.stop_name} ({self.screen_id})"


class StationScreen(Screen):
    station = models.ForeignKey(Stop, on_delete=models.CASCADE)
    station_slug = models.SlugField(unique=True)

    def __str__(self):
        return f"{self.station.stop_name} ({self.screen_id})"


class VehicleScreen(Screen):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    vehicle_slug = models.SlugField(unique=True)

    def __str__(self):
        return f"{self.vehicle.vehicle_label} ({self.screen_id})"
