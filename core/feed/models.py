from django.db import models

# Create your models here.


class InfoProvider(models.Model):
    """Information services providers registered in the system"""

    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name


class InfoService(models.Model):
    """Information services registered in the system"""

    TYPE_CHOICES = [
        ("website", "Sitio web"),
        ("screens", "Sistema de pantallas"),
        ("analysis", "Análisis de datos"),
        ("app", "Aplicación móvil"),
        ("chatbot", "Chatbot"),
        ("social", "Redes sociales"),
        ("other", "Otro"),
    ]
    name = models.CharField(max_length=100)
    description = models.TextField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    provider = models.ForeignKey(InfoProvider, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
