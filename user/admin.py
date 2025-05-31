from django.contrib import admin
from .models import Applicant,Application,Company,Job,Notification

admin.site.register(Application)
admin.site.register(Applicant)
admin.site.register(Company)
admin.site.register(Job)
admin.site.register(Notification)