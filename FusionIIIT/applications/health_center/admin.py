from django.contrib import admin

from .models import *

admin.site.register(Doctor)
# admin.site.register(Appointment)
# admin.site.register(Ambulance_request)
# admin.site.register(Hospital_admit)
# admin.site.register(Complaint)
admin.site.register(Present_Stock)
# admin.site.register(Counter)
# admin.site.register(Expiry)
# admin.site.register(Hospital)
admin.site.register(All_Prescription)
admin.site.register(All_Medicine)
admin.site.register(All_Prescribed_medicine)
admin.site.register(Doctors_Schedule)
admin.site.register(Pathologist_Schedule)
# admin.site.register(Announcements)
# admin.site.register(SpecialRequest)
admin.site.register(Pathologist) 

class InventoryRequisitionItemInline(admin.TabularInline):
    model = InventoryRequisitionItem
    extra = 1

@admin.register(InventoryRequisition)
class InventoryRequisitionAdmin(admin.ModelAdmin):
    list_display = ('id', 'originator', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    inlines = [InventoryRequisitionItemInline]