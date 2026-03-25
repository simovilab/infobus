from django.contrib import admin
from .models import InfoProvider, InfoService

# Register your models here.

admin.site.register(InfoProvider)
admin.site.register(InfoService)
