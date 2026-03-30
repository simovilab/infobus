from django.contrib.gis.db import models

# Create your models here.


class Weather(models.Model):
    """Weather conditions for a specific time and location.

    TODO: buscar APIs de referencia para completar el modelo de esta clase. El objetivo es: proveer datos para cada ubicación (paradas, estaciones, etc.) actuales y para la siguiente hora o más o menos. Ejemplos útiles de variables: temperatura, probabilidad de lluvia, radiación UV. Nota: no todos los datos son para desplegar en pantallas, hay también que pueden ser útiles para investigación.
    """

    id = models.BigAutoField(primary_key=True)
    weather_id = models.CharField(
        max_length=255, help_text="Identificador único de la condición climática."
    )
    weather_date = models.DateField(help_text="Fecha de la condición climática.")
    weather_time = models.TimeField(help_text="Hora de la condición climática.")
    weather_location = models.CharField(
        max_length=255, help_text="Ubicación de la condición climática."
    )
    weather_condition = models.CharField(
        max_length=255, help_text="Condición climática."
    )
    temperature = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Temperatura."
    )
    humidity = models.DecimalField(max_digits=5, decimal_places=2, help_text="Humedad.")
    wind_speed = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Velocidad del viento."
    )
    wind_direction = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Dirección del viento."
    )
    precipitation = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Precipitación."
    )
    visibility = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Visibilidad."
    )
    pressure = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Presión atmosférica."
    )

    def __str__(self):
        return self.weather_id


class CommonAlert(models.Model):
    """Common alerts for a specific time and location based on the Common Alerting Protocol (CAP) specification ITU X.1303."""

    id = models.BigAutoField(primary_key=True)
    


class Social(models.Model):
    """Social media posts for a specific time and location.
    Maps to social.txt in the GTFS feed.

    TODO: sugerencia: utilizar el API de Twitter como referencia para completar el modelo de esta clase. El objetivo es: recopilar datos de un hashtag o de una cuenta de Twitter y mostrarlos en la pantalla de información de la parada o estación.

    En general queremos poner textos de tweets ligados a temas relevantes y posiblemente filtrados para usuarios autorizados o bien algún otro método de filtrado (ejemplo: por geolocalización, sin malas palabras, etc.).

    Referencia: https://developer.x.com/en/docs/twitter-api/tweets/lookup/quick-start

    Nota: probar el API de Twitter antes para verificar qué resultados se obtienen y cómo se pueden filtrar.
    """

    id = models.BigAutoField(primary_key=True)
    social_id = models.CharField(
        max_length=255,
        help_text="Identificador único de la publicación en redes sociales.",
    )
    social_date = models.DateField(
        help_text="Fecha de la publicación en redes sociales."
    )
    social_time = models.TimeField(
        help_text="Hora de la publicación en redes sociales."
    )
    social_location = models.CharField(
        max_length=255, help_text="Ubicación de la publicación en redes sociales."
    )
    social_content = models.TextField(
        help_text="Contenido de la publicación en redes sociales."
    )
    social_media = models.CharField(max_length=255, help_text="Red social.")
    social_likes = models.PositiveIntegerField(help_text="Número de likes.")
    social_shares = models.PositiveIntegerField(help_text="Número de compartidos.")
    social_comments = models.PositiveIntegerField(help_text="Número de comentarios.")

    def __str__(self):
        return self.social_id

