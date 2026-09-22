from django.contrib import admin

from .models import Feedback, Promotion, Service


admin.site.register(Service)
admin.site.register(Promotion)
admin.site.register(Feedback)
