from django.contrib import admin
from mess.scheduling.models import Job, Task, Timecard

class TaskAdmin(admin.ModelAdmin):
    list_filter = ['deadline']

admin.site.register(Job)
admin.site.register(Task, TaskAdmin)
admin.site.register(Timecard)
