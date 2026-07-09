from django.contrib import admin
from .models import Weather, Social, CommonAlert

# Register your models here.


admin.site.register(Weather)
admin.site.register(Social)
admin.site.register(CommonAlert)
